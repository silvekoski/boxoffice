#!/bin/bash
# Bare-metal Isaac setup on a Verda VM (no aalto-sim image tarball needed).
# Upstream cloud/setup_instance.sh pins packages with isaac-constraints.txt, but several pins conflict with what
# isaacsim 6.2.0.0 / Isaac Lab 3.0 ask for (seen 2026-11-13: click, urllib3, psutil, llvmlite, fsspec,
# rerun-sdk). This wrapper runs the setup; on a pip conflict it drops the pin named in the
# "The user requested (constraint) X==B" line and retries. Done steps are skipped on each retry.
#
#   bash sim/setup_fixloop.sh /root/work/upstream     # on the VM, after `pnpm j gpu push <vm> ../aalto-humanoid/upstream`
set -u
UP=${1:-/root/work/upstream}
cd "$UP"
C=aaltonomous/cloud/isaac-constraints.txt
for i in $(seq 1 40); do
  if bash aaltonomous/cloud/setup_instance.sh > /root/setup_try.log 2>&1; then
    echo "SETUP OK after $i tries"; cp /root/setup_try.log /root/setup_ok.log; exit 0
  fi
  cat /root/setup_try.log >> /root/setup_all.log
  line=$(grep -m1 "(constraint)" /root/setup_try.log)
  if [[ -z "$line" ]]; then
    echo "non-constraint failure, see /root/setup_try.log"; tail -30 /root/setup_try.log; exit 1
  fi
  pkg=$(echo "$line" | sed -E 's/.*\(constraint\) ([A-Za-z0-9_.-]+).*/\1/')
  if ! grep -qiE "^${pkg}==" "$C"; then
    echo "constraint for $pkg already removed but still conflicting: $line"; exit 1
  fi
  echo "try $i: $line -> unpin $pkg"
  sed -i -E "/^${pkg}==/Id" "$C"
done
exit 1
