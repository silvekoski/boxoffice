#!/bin/bash
# On the Verda VM after sim/setup_fixloop.sh: start the sim, check the scene, build our image, score it.
#
#   bash /root/work/aalto-humanoid/sim/run_eval.sh [trials] [tasks...]     # default 3 trials, sort_fixed sort_language
#
# Expects /root/work/upstream (the sim install) and /root/work/aalto-humanoid (pnpm j gpu push ../aalto-humanoid).
# Results: /root/work/upstream/runs/eval/<name>_<task>_<variant>_<ts>/eval.json; a summary goes to stdout.
# WARNING (2026-11-15): on Verda VMs the default (non-instance) sim streamed no head-camera frames ("head_camera
# produced no new frames"), so every policy saw a black frame. Use sim/par_eval.sh (instance sims) instead.
set -uo pipefail
TRIALS=${1:-3}; shift || true
TASKS=("${@:-sort_fixed sort_language}")
UP=/root/work/upstream
ME=/root/work/aalto-humanoid
AALTO="bash $UP/aaltonomous/cloud/aalto.sh"

(cd "$ME" && docker build -q -t junction-sorter:dev .) || { echo "docker build failed"; exit 1; }
$AALTO sim || { echo "sim failed"; tail -50 /tmp/aalto_sim.log; exit 1; }     # no-op when already running
$AALTO check | tail -12
for task in ${TASKS[@]}; do
  echo "=== eval $task, $TRIALS trials"
  # --policy is required next to --container: evaluate.py checks --policy (default "oracle") first and would
  # otherwise score the organisers' privileged oracle instead of our image (happened on 2026-11-13).
  (cd "$UP" && $AALTO eval --container junction-sorter:dev --policy ws://localhost:8000 --host-port 8000 \
      --team junction --task "$task" --trials "$TRIALS") 2>&1 | tee /tmp/eval_$task.log | tail -25
  if grep -q "'name': 'oracle'" /tmp/eval_$task.log; then echo "ERROR: the oracle ran, not our image"; exit 3; fi
done
