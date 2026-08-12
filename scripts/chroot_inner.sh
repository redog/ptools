#!/usr/bin/env bash
# Runs *inside* the stage3 chroot; driven by chroot_validate.sh.
# Produces the evidence recorded in docs/gentoo-validation.md.
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PS1='(chroot) '
ANCHOR=sys-apps/portage

echo "===== 0. select a profile if the stage3 has none ====="
if [ ! -e /etc/portage/make.profile ]; then
    PROFILE=$(eselect profile list | grep -m1 'default/linux/amd64/[0-9.]* ' | sed 's/.*\(default[^ ]*\).*/\1/')
    echo "selecting profile: ${PROFILE}"
    eselect profile set "${PROFILE}"
fi
readlink -f /etc/portage/make.profile

echo "===== 0b. reset managed state from any previous run ====="
# The chroot is reused across runs. Without this, steps 5 and 11 would report
# leftovers from the last run ("managed: ~amd64", "no change") instead of
# producing the evidence they exist to produce.
rm -rf /etc/portage/package.use /etc/portage/package.accept_keywords
echo "cleared /etc/portage/package.use and /etc/portage/package.accept_keywords"

echo "===== 1. host facts ====="
python3 --version
python3 -c "import portage; print('portage', portage.VERSION)"
python3 -c "import portage; print('profile', portage.settings.profile_path)"

echo "===== 2. build a test venv ====="
cd /opt/ptools
python3 -m venv --system-site-packages /opt/venv 2>/dev/null || {
    python3 -m venv --system-site-packages --without-pip /opt/venv
    curl -sSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
    /opt/venv/bin/python /tmp/get-pip.py -q
}
/opt/venv/bin/pip install -q pytest pytest-cov
/opt/venv/bin/pip install -q -e .
chmod -R a+rX /opt/venv /opt/ptools
/opt/venv/bin/python -c "import portage, ptools; print('portage visible inside the venv')"

echo "===== 3. integration test suite ====="
/opt/venv/bin/python -m pytest -m integration --no-cov -q

echo "===== 4. environment discovery ====="
/opt/venv/bin/python scripts/discover_environment.py | tee /opt/environment.md

echo "===== 5. read-only operation as a non-root user ====="
su -s /bin/sh nobody -c "/opt/venv/bin/puse $ANCHOR"
su -s /bin/sh nobody -c "/opt/venv/bin/pkw $ANCHOR"

echo "===== 6. non-root dry-run writes nothing ====="
rm -rf /etc/portage/package.use
su -s /bin/sh nobody -c "/opt/venv/bin/puse --dry-run $ANCHOR doc"
if [ -e /etc/portage/package.use ]; then
    echo "FAIL: dry-run created /etc/portage/package.use"; exit 1
fi
echo "OK: /etc/portage/package.use still absent after the dry-run"

echo "===== 7. non-root write is refused with exit 5 ====="
mkdir -p /etc/portage/package.use
chmod 0755 /etc/portage/package.use
set +e
su -s /bin/sh nobody -c "/opt/venv/bin/puse $ANCHOR doc"
echo "exit=$?  (expected 5)"
set -e

echo "===== 8. chroot write preserves the rest of the file ====="
printf '# hand written, must survive\n\napp-shells/bash net\n' > /etc/portage/package.use/ptools
FLAG=$(/opt/venv/bin/python scripts/verify_consumption.py pick "$ANCHOR")
echo "candidate flag: $FLAG"
set +e
/opt/venv/bin/python scripts/verify_consumption.py check "$ANCHOR" "$FLAG"
echo "  (exit=$? before the write; non-zero is expected)"
set -e

/opt/venv/bin/puse "$ANCHOR" "$FLAG"
echo "--- /etc/portage/package.use/ptools ---"
cat /etc/portage/package.use/ptools
echo "---"

echo "===== 9. portage consumes the generated entry ====="
/opt/venv/bin/python scripts/verify_consumption.py check "$ANCHOR" "$FLAG"

echo "===== 10. idempotency, then unset ====="
/opt/venv/bin/puse --json "$ANCHOR" "$FLAG"
/opt/venv/bin/puse --unset "$ANCHOR" "$FLAG"
cat /etc/portage/package.use/ptools

echo "===== 11. keyword write + portage acceptance ====="
/opt/venv/bin/pkw --testing "$ANCHOR"
cat /etc/portage/package.accept_keywords/ptools

echo "===== 12. a REAL flat package.use file is refused, not clobbered ====="
# The flat layout is a legitimate portage configuration, so ptools must refuse
# it (exit 6) rather than replace the file with a directory. Seed it with $FLAG
# and let portage confirm it honours the flat file before ptools ever runs.
rm -rf /etc/portage/package.use
printf '# flat layout, hand written\napp-shells/bash net\n%s %s\n' "$ANCHOR" "$FLAG" \
    > /etc/portage/package.use
/opt/venv/bin/python scripts/verify_consumption.py check "$ANCHOR" "$FLAG"

# $FLAG is enabled now, so `pick` necessarily returns a different flag.
FLAG2=$(/opt/venv/bin/python scripts/verify_consumption.py pick "$ANCHOR")
echo "second candidate flag: $FLAG2"
BEFORE=$(sha256sum /etc/portage/package.use | cut -d' ' -f1)
set +e
/opt/venv/bin/puse "$ANCHOR" "$FLAG2"
RC=$?
set -e
echo "exit=$RC  (expected 6)"
[ "$RC" -eq 6 ] || { echo "FAIL: expected exit 6 under a flat layout"; exit 1; }
[ -f /etc/portage/package.use ] || { echo "FAIL: flat file is no longer a file"; exit 1; }
AFTER=$(sha256sum /etc/portage/package.use | cut -d' ' -f1)
[ "$BEFORE" = "$AFTER" ] || { echo "FAIL: flat file was modified"; exit 1; }
echo "OK: flat file byte-identical after the refusal"

# Reading must still work under a flat layout: it goes through portage, not the
# managed target, and portage's own USE evaluation includes the flat entry.
/opt/venv/bin/puse "$ANCHOR"

echo "===== ALL CHECKS COMPLETE ====="
