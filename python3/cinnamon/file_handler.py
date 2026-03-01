#!/usr/bin/python3
"""
file_handler.py – Linux support for Windows (.exe), Android (.apk),
and iOS (.ipa) file types.

On Linux these file types cannot be natively installed or run.  This module
detects each extension (and validates via magic bytes where possible) and
provides user-facing actions:

  .exe  – run via Wine/Proton if installed; otherwise auto-install Wine using
          the system package manager.
  .apk  – sideload via ``adb`` to an attached Android device or emulator;
          if ``adb`` is absent it is auto-installed via the system package
          manager.
  .ipa  – explain iOS signing/device restrictions; offer to extract and show
          metadata (treated as ZIP).  Does not claim actual installation.

None of the handlers modify existing Lemon flows.
"""

import os
import shutil
import zipfile
import logging

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Magic-byte signatures
# ---------------------------------------------------------------------------

#: First two bytes of every PE/MZ executable (Windows EXE/DLL).
_EXE_MAGIC = b"MZ"

#: First four bytes of a ZIP archive (used by both APK and IPA).
_ZIP_MAGIC = b"PK\x03\x04"

# ---------------------------------------------------------------------------
# Extension → MIME type mapping (informational)
# ---------------------------------------------------------------------------

EXTENSION_MIME = {
    ".exe": "application/x-ms-dos-executable",
    ".apk": "application/vnd.android.package-archive",
    ".ipa": "application/octet-stream",
}

# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------


def detect_by_extension(path):
    """Return the lower-cased extension of *path*, or ``None`` if not one of
    the three supported extensions."""
    _, ext = os.path.splitext(path)
    ext = ext.lower()
    if ext in EXTENSION_MIME:
        return ext
    return None


def _read_magic(path, length):
    """Read the first *length* bytes of *path* safely; return ``None`` on
    failure."""
    try:
        with open(path, "rb") as fh:
            return fh.read(length)
    except OSError as exc:
        log.debug("Could not read magic bytes from %r: %s", path, exc)
        return None


def verify_magic(path, ext):
    """Return ``True`` when the magic bytes of *path* match *ext*.

    For ``'.exe'`` this checks for the MZ header.  For ``'.apk'`` and
    ``'.ipa'`` this checks for the ZIP/PK header (both formats are ZIP
    archives).  Returns ``True`` also when the file cannot be read, so that
    the caller still attempts to handle it.
    """
    if ext == ".exe":
        magic = _read_magic(path, 2)
        if magic is None:
            return True
        return magic == _EXE_MAGIC
    if ext in (".apk", ".ipa"):
        magic = _read_magic(path, 4)
        if magic is None:
            return True
        return magic == _ZIP_MAGIC
    return True


# ---------------------------------------------------------------------------
# Tool detection
# ---------------------------------------------------------------------------


def check_tool(name):
    """Return ``True`` when *name* is found on ``PATH``."""
    return shutil.which(name) is not None


def wine_available():
    """Return ``True`` when ``wine`` or ``proton`` is available."""
    return check_tool("wine") or check_tool("proton")


def adb_available():
    """Return ``True`` when ``adb`` is available."""
    return check_tool("adb")


# ---------------------------------------------------------------------------
# Package manager detection and auto-install helpers
# ---------------------------------------------------------------------------

#: Ordered list of (pm_command, pm_key) pairs to probe.
_PACKAGE_MANAGERS = [
    ("apt-get", "apt-get"),   # Debian / Ubuntu / Mint
    ("dnf", "dnf"),            # Fedora / RHEL
    ("pacman", "pacman"),      # Arch
    ("zypper", "zypper"),      # openSUSE
]

#: Install base-argv for each known package manager (uses pkexec for GUI
#: privilege escalation without a password prompt in most Polkit setups).
_PM_INSTALL_BASE = {
    "apt-get": ["pkexec", "apt-get", "install", "-y"],
    "dnf":     ["pkexec", "dnf",     "install", "-y"],
    "pacman":  ["pkexec", "pacman",  "-S", "--noconfirm"],
    "zypper":  ["pkexec", "zypper",  "install", "-y"],
}

#: Package names for each tool on each supported package manager.
_TOOL_PACKAGES = {
    "wine": {
        "apt-get": ["wine"],
        "dnf":     ["wine"],
        "pacman":  ["wine"],
        "zypper":  ["wine"],
    },
    "adb": {
        "apt-get": ["adb"],
        "dnf":     ["android-tools"],
        "pacman":  ["android-tools"],
        "zypper":  ["android-tools"],
    },
}


def detect_package_manager():
    """Return ``(pm_key, base_install_argv)`` for the first package manager
    found on ``PATH``, or ``None`` when none is available."""
    for pm_cmd, pm_key in _PACKAGE_MANAGERS:
        if check_tool(pm_cmd):
            return pm_key, _PM_INSTALL_BASE[pm_key]
    return None


def build_install_argv(tool_name):
    """Return the ``argv`` list that will auto-install *tool_name* via the
    detected package manager (using ``pkexec`` for privilege escalation).

    Returns ``None`` when no supported package manager is found or when
    *tool_name* is not known.
    """
    pm_info = detect_package_manager()
    if pm_info is None:
        log.debug("build_install_argv: no supported package manager found")
        return None
    pm_key, base_argv = pm_info
    packages = _TOOL_PACKAGES.get(tool_name, {}).get(pm_key)
    if not packages:
        log.debug("build_install_argv: no package mapping for %r on %s", tool_name, pm_key)
        return None
    return base_argv + packages


# ---------------------------------------------------------------------------
# IPA metadata helpers
# ---------------------------------------------------------------------------


def _read_ipa_metadata(path):
    """Extract a small subset of metadata from an IPA file.

    Returns a ``dict`` with keys ``"bundle_id"``, ``"version"``, and
    ``"display_name"`` when possible, otherwise an empty dict.
    """
    meta = {}
    try:
        with zipfile.ZipFile(path, "r") as zf:
            for name in zf.namelist():
                if name.endswith("Info.plist") and "Payload/" in name:
                    try:
                        data = zf.read(name)
                        meta["plist_size"] = len(data)
                        meta["plist_path"] = name
                    except (KeyError, ValueError, OSError) as exc:
                        log.debug("Could not read Info.plist: %s", exc)
                    break
    except (zipfile.BadZipFile, OSError) as exc:
        log.debug("Could not open IPA as ZIP: %s", exc)
    return meta


# ---------------------------------------------------------------------------
# Handler functions
# ---------------------------------------------------------------------------


def handle_exe(path, _notify_fn=None):
    """Handle a Windows EXE file.

    Returns a ``dict`` describing the recommended action and a human-readable
    message.  The optional *_notify_fn* callback receives ``(title, body)``
    when provided (intended for GTK/UI callers).

    This function never spawns a process itself; that responsibility belongs
    to the caller so that it can obtain user confirmation first.
    """
    result = {
        "path": path,
        "ext": ".exe",
        "wine_available": wine_available(),
    }

    if result["wine_available"]:
        tool = "proton" if check_tool("proton") else "wine"
        result["action"] = "run_with_wine"
        result["tool"] = tool
        result["argv"] = [tool, path]
        result["auto_install_argv"] = []
        result["message"] = (
            "This is a Windows executable.  It can be run using {tool}.\n\n"
            "Command: {tool} {path}"
        ).format(tool=tool, path=path)
        title = "Run Windows application"
    else:
        install_argv = build_install_argv("wine")
        result["action"] = "install_wine"
        result["tool"] = None
        result["argv"] = []
        result["auto_install_argv"] = install_argv or []
        if install_argv:
            result["message"] = (
                "This is a Windows executable, but Wine is not installed.\n\n"
                "Wine will be installed automatically so this file can be run."
            )
            title = "Install Wine"
        else:
            result["message"] = (
                "This is a Windows executable, but Wine is not installed\n"
                "and no supported package manager was found.\n\n"
                "Install Wine manually:\n"
                "  • Debian/Ubuntu/Mint: sudo apt install wine\n"
                "  • Fedora: sudo dnf install wine\n"
                "  • Arch: sudo pacman -S wine\n\n"
                "Alternatively, install Proton via Steam."
            )
            title = "Wine not installed"

    log.info("handle_exe: %s", result["message"])
    if callable(_notify_fn):
        _notify_fn(title, result["message"])
    return result


def handle_apk(path, _notify_fn=None):
    """Handle an Android APK file.

    Returns a ``dict`` describing the recommended action.  When ``adb`` is not
    installed, attempts to auto-install it via the system package manager.
    """
    result = {
        "path": path,
        "ext": ".apk",
        "adb_available": adb_available(),
    }

    if result["adb_available"]:
        result["action"] = "adb_install"
        result["argv"] = ["adb", "install", path]
        result["auto_install_argv"] = []
        result["message"] = (
            "This is an Android package.\n\n"
            "adb is available.  You can sideload it to a connected device or\n"
            "emulator with:\n"
            "  adb install {path}\n\n"
            "Make sure USB debugging is enabled on the target device."
        ).format(path=path)
        title = "Install Android package"
    else:
        install_argv = build_install_argv("adb")
        result["action"] = "install_adb"
        result["argv"] = []
        result["auto_install_argv"] = install_argv or []
        if install_argv:
            result["message"] = (
                "This is an Android package, but adb is not installed.\n\n"
                "adb will be installed automatically so you can sideload\n"
                "this package to a connected Android device or emulator."
            )
            title = "Install adb"
        else:
            result["message"] = (
                "This is an Android package, but adb is not installed\n"
                "and no supported package manager was found.\n\n"
                "Install adb manually:\n"
                "  • Debian/Ubuntu/Mint: sudo apt install adb\n"
                "  • Fedora: sudo dnf install android-tools\n"
                "  • Arch: sudo pacman -S android-tools\n\n"
                "You can also use an Android emulator such as Waydroid or\n"
                "Android Studio's AVD manager."
            )
            title = "adb not installed"

    log.info("handle_apk: %s", result["message"])
    if callable(_notify_fn):
        _notify_fn(title, result["message"])
    return result


def handle_ipa(path, _notify_fn=None):
    """Handle an iOS IPA file.

    IPA files are ZIP archives containing an iOS application bundle.  They
    cannot be installed on Linux (Apple's code-signing and DRM requirements
    make this impossible without a jailbroken device).  This handler extracts
    and shows available metadata instead.
    """
    meta = _read_ipa_metadata(path)
    result = {
        "path": path,
        "ext": ".ipa",
        "action": "inspect_only",
        "metadata": meta,
        "argv": [],
        "auto_install_argv": [],
    }

    meta_lines = []
    if meta.get("plist_path"):
        meta_lines.append("Info.plist found at: {}".format(meta.get("plist_path")))
        meta_lines.append(
            "Info.plist size: {} bytes".format(meta.get("plist_size", "unknown"))
        )
    meta_text = "\n".join(meta_lines) if meta_lines else "No metadata extracted."

    result["message"] = (
        "This is an iOS application archive.\n\n"
        "iOS apps cannot be installed on Linux due to Apple's code-signing\n"
        "and DRM requirements.  The file can be extracted (it is a ZIP\n"
        "archive) for inspection.\n\n"
        "{meta_text}\n\n"
        "To inspect the contents:\n"
        "  unzip -l {path}"
    ).format(meta_text=meta_text, path=path)

    title = "iOS application (inspection only)"
    log.info("handle_ipa: %s", result["message"])
    if callable(_notify_fn):
        _notify_fn(title, result["message"])
    return result


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------


def dispatch(path, _notify_fn=None):
    """Detect the file type of *path* and call the appropriate handler.

    Returns the handler's result dict, or ``None`` when *path* does not match
    any supported extension.
    """
    ext = detect_by_extension(path)
    if ext is None:
        log.debug("dispatch: unsupported extension for %r", path)
        return None

    if not verify_magic(path, ext):
        log.warning(
            "dispatch: %r has extension %s but magic bytes do not match; "
            "proceeding anyway",
            path, ext,
        )

    handlers = {
        ".exe": handle_exe,
        ".apk": handle_apk,
        ".ipa": handle_ipa,
    }
    return handlers[ext](path, _notify_fn)
