#!/bin/bash
# Parallel sim eval on a multi-GPU Verda VM (after sim/setup_fixloop.sh): one isolated sim instance per GPU, each
# scoring our image on a block of seeds. Used for results/sim-dr-2026-11-14 (8x RTX PRO 6000, 3 trials x 8, ~55 min).
#
#   IMAGE=junction-sorter:v2 bash /root/work/aalto-humanoid/sim/par_eval.sh [trials_per_instance=3] [instances_per_task=4]
# Instances share GPUs round-robin when there are fewer GPUs than instances (CPU becomes the limit: ~1 sim per 30 vCPU).
#
# Instance i: GPU i, DDS domain 10+i, cams 56000+20i.., rgbd +10, scene +15 (clock +16), teleimager request port
# 61000+i, policy container on :8100+i. TASK must be Aalto-* or run_sim.sh skips the instance isolation.
# Not a .CC (confidential compute) VM: those have no Vulkan.
set -u
TPI=${1:-3}; IPT=${2:-4}
UP=/root/work/upstream; ME=/root/work/aalto-humanoid; cd $UP
IMAGE=${IMAGE:-junction-sorter:dev}          # built from $ME unless SKIP_BUILD=1 (e.g. a loaded submission tarball)
NGPU=$(nvidia-smi -L | wc -l)
[[ "${SKIP_BUILD:-0}" == 1 ]] || (cd "$ME" && docker build -q -t "$IMAGE" .) || { echo "docker build failed"; exit 1; }
source /root/miniforge3/etc/profile.d/conda.sh; conda activate isaac
export AALTO_DR=${AALTO_DR:-train} PYTHONPATH=$UP OMNI_KIT_ACCEPT_EULA=YES TASK=Aalto-Sort-G129-Dex3-Joint
i=0
for task in sort_fixed sort_language; do
  for k in $(seq 0 $((IPT-1))); do
    seed=$((1000 + k*TPI))
    (
      export AALTO_INSTANCE=i$i AALTO_DDS_DOMAIN=$((10+i)) AALTO_CAM_PORT_BASE=$((56000+20*i)) \
             AALTO_RGBD_PORT=$((56010+20*i)) AALTO_SCENE_PORT=$((56015+20*i)) \
             CUDA_VISIBLE_DEVICES=$((i % NGPU)) AALTO_TELEIMAGER_REQ_PORT=$((61000+i))
      nohup bash aaltonomous/sim/run_sim.sh > /root/sim_i$i.log 2>&1 &
      sleep 60; for _ in $(seq 300); do python -m aaltonomous.sim.scene_client ping >/dev/null 2>&1 && break; sleep 3; done
      port=$((8100+i))
      # --policy next to --container, or evaluate.py scores the oracle (see run_eval.sh)
      python -m aaltonomous.sim.evaluate --container $IMAGE --policy ws://localhost:$port --host-port $port \
        --team junction --task $task --trials $TPI --seed $seed --out runs/eval_par/i$i > /root/eval_i$i.log 2>&1
      rc=$?
      grep -q "'name': 'oracle'" /root/eval_i$i.log && { echo "i$i ERROR: the oracle ran, not our image"; rc=3; }
      echo "i$i $task seed $seed: eval exit $rc $(date -u +%T)"
    ) &
    i=$((i+1)); sleep 5
  done
done
wait
echo PAR_DONE
