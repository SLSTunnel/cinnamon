Cinnamon is a Linux desktop that provides advanced innovative features and a traditional user experience.

The desktop layout is similar to GNOME 2 with underlying technology forked from the GNOME Shell.
Cinnamon makes users feel at home with an easy-to-use and comfortable desktop experience.


Contributing
============
Cinnamon is on GitHub at https://github.com/SLSTunnel/cinnamon.

Note that some issues may not be with Cinnamon itself. For a list of related components,
please see https://projects.linuxmint.com/cinnamon/.


Handling Windows, Android, and iOS files
=========================================
Cinnamon includes support for opening the following file types on Linux via
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
modify existing Cinnamon flows or change the behaviour of already-supported
file types.


License
=======
Cinnamon is distributed under the terms of the GNU General Public License,
version 2 or later. See the COPYING file for details.

