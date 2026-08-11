#!/usr/bin/env bash
# Validate ptools against real portage inside a Gentoo stage3 chroot.
#
#   sudo scripts/chroot_validate.sh /var/tmp/ptools-chroot
#
# The directory must already contain dl/stage3.tar.xz and dl/portage-latest.tar.xz.
# Nothing outside $CHROOT is written: the host's /etc/portage is never touched.
set -euo pipefail

CHROOT="${1:?usage: chroot_validate.sh <chroot-dir>}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

case "$CHROOT" in
    /|/etc|/usr|/var|/home) echo "refusing to use $CHROOT as a chroot" >&2; exit 1 ;;
esac
[[ -f "$CHROOT/dl/stage3.tar.xz" ]] || { echo "missing $CHROOT/dl/stage3.tar.xz" >&2; exit 1; }

cleanup() {
    for mp in dev/pts dev proc sys; do
        mountpoint -q "$CHROOT/$mp" && umount -l "$CHROOT/$mp" || true
    done
}
trap cleanup EXIT

if [[ ! -x "$CHROOT/usr/bin/python3" ]]; then
    echo "== extracting stage3"
    tar xpf "$CHROOT/dl/stage3.tar.xz" --xattrs-include='*.*' --numeric-owner -C "$CHROOT"
fi

if [[ ! -d "$CHROOT/var/db/repos/gentoo/sys-apps/portage" ]]; then
    echo "== extracting the ebuild repository"
    mkdir -p "$CHROOT/var/db/repos"
    tar xpf "$CHROOT/dl/portage-latest.tar.xz" -C "$CHROOT/var/db/repos"
    rm -rf "$CHROOT/var/db/repos/gentoo"
    mv "$CHROOT/var/db/repos/portage" "$CHROOT/var/db/repos/gentoo"
fi

echo "== staging the working tree"
rm -rf "$CHROOT/opt/ptools"
mkdir -p "$CHROOT/opt/ptools"
tar -C "$REPO" --exclude=.git --exclude=.venv --exclude=.tools --exclude=dist \
    --exclude=__pycache__ --exclude='.*_cache' -cf - . | tar -C "$CHROOT/opt/ptools" -xf -
chmod -R a+rX "$CHROOT/opt/ptools"
cp -L /etc/resolv.conf "$CHROOT/etc/resolv.conf"
install -m 0755 "$REPO/scripts/chroot_inner.sh" "$CHROOT/opt/chroot_inner.sh"

echo "== mounting"
mount --types proc /proc "$CHROOT/proc"
mount --rbind /sys "$CHROOT/sys" && mount --make-rslave "$CHROOT/sys"
mount --rbind /dev "$CHROOT/dev" && mount --make-rslave "$CHROOT/dev"

echo "== entering the chroot"
chroot "$CHROOT" /opt/chroot_inner.sh
