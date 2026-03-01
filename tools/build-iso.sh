#!/usr/bin/env bash
# build-iso.sh – Build a bootable live ISO containing the Lemon desktop.
#
# Requirements
# ------------
#   Debian / Ubuntu / Linux Mint host (live-build is Debian-specific).
#   Packages: live-build xorriso squashfs-tools debootstrap
#
# Usage
# -----
#   sudo ./tools/build-iso.sh [--arch ARCH] [--suite SUITE] [--output DIR]
#
#   --arch   CPU architecture (default: amd64)
#   --suite  Debian/Ubuntu suite (default: noble)
#   --output Directory where the finished .iso is placed (default: build/iso)
#
# The finished image is written to:
#   <output>/<suite>-lemon-<arch>.iso
#
# NOTE: live-build must be run as root (or via sudo) because it chroots into
#       the build environment.

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
ARCH="amd64"
SUITE="noble"
OUTPUT_DIR="build/iso"

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --arch)   ARCH="$2";       shift 2 ;;
        --suite)  SUITE="$2";      shift 2 ;;
        --output) OUTPUT_DIR="$2"; shift 2 ;;
        -h|--help)
            sed -n '/^# build-iso/,/^[^#]/{ /^[^#]/d; s/^# \{0,1\}//; p }' "$0"
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

ISO_NAME="${SUITE}-lemon-${ARCH}.iso"

# Resolve the repo root now, while the working directory is still wherever
# the caller ran the script from (i.e. before we cd into the temp build dir).
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ---------------------------------------------------------------------------
# Ubuntu vs Debian mode detection
# ---------------------------------------------------------------------------
# live-build defaults to Debian mode; Ubuntu suites require --mode ubuntu and
# Ubuntu-specific mirror URLs.  Architectures in the "main" Ubuntu archive
# (amd64 / i386) are served from archive.ubuntu.com; everything else uses the
# ports mirror.
UBUNTU_SUITES=(bionic focal jammy lunar mantic noble oracular plucky)  # update as new Ubuntu LTS/interim releases are published
LB_MODE="debian"
LB_MIRROR="http://deb.debian.org/debian/"
for _us in "${UBUNTU_SUITES[@]}"; do
    if [[ "$SUITE" == "$_us" ]]; then
        LB_MODE="ubuntu"
        if [[ "$ARCH" == "amd64" || "$ARCH" == "i386" ]]; then
            LB_MIRROR="http://archive.ubuntu.com/ubuntu/"
        else
            LB_MIRROR="http://ports.ubuntu.com/ubuntu-ports/"
        fi
        break
    fi
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()  { echo "[build-iso] $*"; }
die()  { echo "[build-iso] ERROR: $*" >&2; exit 1; }

require_cmd() {
    command -v "$1" &>/dev/null || die "'$1' not found. Install it with: $2"
}

require_root() {
    [[ $EUID -eq 0 ]] || die "This script must be run as root (or via sudo)."
}

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
require_root
require_cmd lb         "apt-get install live-build"
require_cmd xorriso    "apt-get install xorriso"
require_cmd mksquashfs "apt-get install squashfs-tools"
require_cmd debootstrap "apt-get install debootstrap"

# ---------------------------------------------------------------------------
# Prepare build directory
# ---------------------------------------------------------------------------
BUILD_DIR="$(mktemp -d /tmp/lemon-iso-XXXXXX)"
trap 'log "Cleaning up $BUILD_DIR"; rm -rf "$BUILD_DIR"' EXIT

log "Build directory : $BUILD_DIR"
log "Architecture    : $ARCH"
log "Suite           : $SUITE"
log "Output          : $OUTPUT_DIR/$ISO_NAME"

cd "$BUILD_DIR"

# ---------------------------------------------------------------------------
# Configure live-build
# ---------------------------------------------------------------------------
lb config \
    --mode           "$LB_MODE" \
    --architectures  "$ARCH" \
    --distribution   "$SUITE" \
    --mirror-bootstrap       "$LB_MIRROR" \
    --mirror-chroot          "$LB_MIRROR" \
    --mirror-binary          "$LB_MIRROR" \
    --binary-images  iso-hybrid \
    --debian-installer live \
    --debian-installer-gui true \
    --archive-areas "main restricted universe multiverse" \
    --apt-recommends true \
    --bootappend-live "boot=live components quiet splash" \
    --iso-application "Lemon Desktop Live" \
    --iso-publisher   "SLSTunnel/lemon" \
    --iso-volume      "LEMON_LIVE"

# ---------------------------------------------------------------------------
# Package lists
# ---------------------------------------------------------------------------
mkdir -p config/package-lists

cat > config/package-lists/lemon.list.chroot <<'EOF'
# Lemon desktop and essentials
lemon
lemon-core
nemo
nemo-fileroller
lightdm
lightdm-gtk-greeter
network-manager-gnome
pulseaudio
pavucontrol
firefox
gedit
gnome-terminal
file-roller
system-config-printer
cups
gparted
timeshift
mintinstall
# Firmware
linux-firmware
b43-fwcutter
# Calamares graphical installer
calamares
calamares-settings-debian
EOF

# ---------------------------------------------------------------------------
# Auto-login for the live session
# ---------------------------------------------------------------------------
# live-build automatically creates a 'user' account (with password 'user') in
# the live environment via the live-config package.  The username below must
# match that auto-created account.  If you customise the live username via
# the --username lb config option, update autologin-user accordingly.
mkdir -p config/includes.chroot/etc/lightdm

cat > config/includes.chroot/etc/lightdm/lightdm.conf <<'EOF'
[Seat:*]
autologin-user=user
autologin-user-timeout=0
user-session=lemon
EOF

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
log "Starting live-build (this may take 20-40 minutes)…"
lb build 2>&1 | tee /tmp/lemon-iso-build.log

# live-build writes the ISO as live-image-*.hybrid.iso in the build dir
BUILT_ISO="$(find "${BUILD_DIR}" -maxdepth 1 -name 'live-image-*.hybrid.iso' 2>/dev/null | head -1)"
[[ -n "$BUILT_ISO" ]] || die "live-build did not produce an ISO. See /tmp/lemon-iso-build.log"

# ---------------------------------------------------------------------------
# Copy to output directory
# ---------------------------------------------------------------------------
DEST="${REPO_ROOT}/${OUTPUT_DIR}"
mkdir -p "$DEST"
cp "$BUILT_ISO" "$DEST/$ISO_NAME"
log "ISO written to: $DEST/$ISO_NAME"
