#!/usr/bin/env bash
# Fetch the organisers' starter repo and the G1 URDF at pinned revisions into aalto-humanoid/upstream/.
# upstream/ is gitignored: it is a pinned clone, not vendored code. Bump UPSTREAM_REV when the organisers
# announce a new version on Discord (v1, v2, ...), then run this script again and rerun the tests.
#
#   bash scripts/fetch_upstream.sh          # idempotent
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UP="$HERE/upstream"

UPSTREAM_URL=https://github.com/zupermiez/aaltonomous-humanoid
UPSTREAM_REV=36daf5b44dad46b8f448a5124ded7faa9947be1e     # main on 2026-11-13 21:54 (aaltonomous VERSION in tree)
XRTELEOP_URL=https://github.com/unitreerobotics/xr_teleoperate.git
XRTELEOP_REV=817fb00c63cde15e5f24a0f8fa08e1e33ed89d3b      # same pin as upstream cloud/setup_instance.sh
URDF=assets/g1/g1_body29_hand14.urdf

clone_at() {  # clone_at <url> <dir> <sha> [sparse path]
    local url=$1 dir=$2 sha=$3 sparse=${4:-}
    if [[ -d "$dir/.git" ]] && [[ "$(git -C "$dir" rev-parse HEAD)" == "$sha" ]]; then return; fi
    rm -rf "$dir"; git init -q "$dir"
    git -C "$dir" remote add origin "$url"
    if [[ -n "$sparse" ]]; then
        git -C "$dir" config core.sparseCheckout true
        echo "$sparse" > "$dir/.git/info/sparse-checkout"
    fi
    git -C "$dir" fetch -q --depth 1 origin "$sha"
    git -C "$dir" -c advice.detachedHead=false checkout -q FETCH_HEAD
}

clone_at "$UPSTREAM_URL" "$UP" "$UPSTREAM_REV"
clone_at "$XRTELEOP_URL" "$UP/third_party/xr_teleoperate" "$XRTELEOP_REV" "$URDF"
test -f "$UP/third_party/xr_teleoperate/$URDF"
echo "upstream at $(git -C "$UP" rev-parse --short HEAD), URDF ok"
