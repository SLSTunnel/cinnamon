Lemon is a Linux desktop that provides advanced innovative features and a traditional user experience.

The desktop layout is similar to GNOME 2 with underlying technology forked from the GNOME Shell.
Lemon makes users feel at home with an easy-to-use and comfortable desktop experience.


Installing via USB
==================

You can run and install the Lemon desktop (via Linux Mint) from a USB
drive by following these steps:

**1. Download a Linux Mint ISO**

Download the latest Linux Mint ISO that ships with Lemon from the official
website: https://linuxmint.com/download.php

Choose the **Lemon** edition and select a mirror to download the ``.iso``
file.

**2. Create a bootable USB drive**

You need a USB drive of at least 4 GB. All existing data on the drive will
be erased.

* **Linux / macOS (dd)**:

  .. warning::
     ``dd`` will **overwrite all data** on the target device.  Triple-check
     that ``/dev/sdX`` is your USB drive and not your system disk before
     running the command.

  ::

    # Find your USB drive device (e.g. /dev/sdX or /dev/diskN)
    lsblk              # Linux
    diskutil list      # macOS

    # Write the ISO — replace /dev/sdX with your actual device
    sudo dd if=/path/to/linuxmint.iso of=/dev/sdX bs=4M status=progress oflag=sync

* **Linux (graphical – Etcher)**:
  Download and run `balenaEtcher <https://etcher.balena.io/>`_, select the
  ISO and target USB drive, then click *Flash*.

* **Windows (Rufus)**:
  Download `Rufus <https://rufus.ie/>`_, select the ISO, choose your USB
  drive, leave the partition scheme as *GPT* (for UEFI — recommended for
  modern computers) or *MBR* (for legacy BIOS systems), and click *Start*.

**3. Boot from the USB drive**

1. Insert the USB drive into the target computer.
2. Restart the computer and enter the boot menu — typically by pressing
   ``F12``, ``F11``, ``Esc``, or ``Del`` during POST (the key shown briefly
   on screen at startup varies by manufacturer).
3. Select the USB drive from the boot menu.
4. Linux Mint will load a live desktop environment where you can try Lemon
   without making any changes to your computer.

**4. Install Lemon / Linux Mint**

1. Once the live desktop has loaded, double-click the
   **Install Linux Mint** icon on the desktop.
2. Follow the on-screen installer:

   * Choose your language and keyboard layout.
   * Optionally install multimedia codecs.
   * Select an installation type (*Erase disk* for a fresh install, or
     *Something else* for manual partitioning alongside an existing OS).
   * Choose your timezone, create a user account, and click *Install*.

3. When installation is complete, restart the computer and remove the USB
   drive when prompted.

After rebooting you will be greeted by the Lemon desktop.

Building a custom ISO
=====================

The script ``tools/build-iso.sh`` builds a bootable live ISO containing the
Lemon desktop using `live-build <https://salsa.debian.org/live-team/live-build>`_.

**Requirements**

* A Debian, Ubuntu, or Linux Mint host (live-build is Debian-specific).
* The following packages installed on the host::

    sudo apt-get install live-build xorriso squashfs-tools debootstrap

**Basic usage**::

    sudo ./tools/build-iso.sh

The finished image is placed in ``build/iso/noble-lemon-amd64.iso``.

**Options**

=====================  ===================================  =========================
Flag                   Description                          Default
=====================  ===================================  =========================
``--arch ARCH``        Target CPU architecture              ``amd64``
``--suite SUITE``      Debian/Ubuntu suite (codename)       ``noble``
``--output DIR``       Directory for the finished ISO       ``build/iso``
=====================  ===================================  =========================

**Examples**::

    # ARM64 image based on Ubuntu 24.04 (noble)
    sudo ./tools/build-iso.sh --arch arm64 --suite noble

    # AMD64 image saved to a custom location
    sudo ./tools/build-iso.sh --output /tmp/my-isos

The script must be run as root (or via ``sudo``) because live-build chroots
into the build environment.  A full build takes 20–40 minutes depending on
network speed and host performance.

Build logs are written to ``/tmp/lemon-iso-build.log``.

Contributing
============
Lemon is on GitHub at https://github.com/SLSTunnel/cinnamon.

Note that some issues may not be with Lemon itself. For a list of related components,
please see https://projects.linuxmint.com/cinnamon/.


Handling Windows, Android, and iOS files
=========================================
Lemon includes support for opening the following file types on Linux via
the ``cinnamon-file-handler`` utility:

`.exe` – Windows executables
  Linux cannot natively run Windows executables.  When ``wine`` or ``proton``
  is installed the handler offers to launch the file with that tool.  If
  neither is present, Wine is **automatically installed** using the system
  package manager (after user confirmation).

  Package installed automatically (if needed):

  * Debian / Ubuntu / Mint: ``wine`` (via ``apt-get``)
  * Fedora / RHEL: ``wine`` (via ``dnf``)
  * Arch: ``wine`` (via ``pacman``)
  * openSUSE: ``wine`` (via ``zypper``)

  Alternatively, Proton can be installed manually via *Steam → Settings →
  Compatibility*.

`.apk` – Android packages
  APK files can be side-loaded to an attached Android device or emulator via
  ``adb``.  When ``adb`` is installed the handler shows the sideload command.
  If ``adb`` is absent it is **automatically installed** via the system
  package manager (after user confirmation).

  Package installed automatically (if needed):

  * Debian / Ubuntu / Mint: ``adb`` (via ``apt-get``)
  * Fedora / RHEL: ``android-tools`` (via ``dnf``)
  * Arch: ``android-tools`` (via ``pacman``)
  * openSUSE: ``android-tools`` (via ``zypper``)

  An Android emulator such as `Waydroid <https://waydroid.com/>`_ or Android
  Studio's AVD manager can also be used.

`.ipa` – iOS application archives
  iOS apps **cannot be installed on Linux** due to Apple's code-signing and
  DRM requirements.  The handler extracts available metadata from the archive
  (IPA files are ZIP archives) and shows a message explaining the limitation.
  No installation is attempted.

Auto-install uses ``pkexec`` for privilege escalation; a Polkit authentication
dialog will appear before any package is installed.  None of these handlers
modify existing Lemon flows or change the behaviour of already-supported
file types.


License
=======
Lemon is distributed under the terms of the GNU General Public License,
version 2 or later. See the COPYING file for details.

