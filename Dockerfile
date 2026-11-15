# Our submission image: SortingPolicy (sorter/) on top of the organisers' classical stack, as a policy server on :8000.
# Based on upstream aaltonomous/docker/submission.Dockerfile + baseline.Dockerfile (CUDA 12.8 base, CPU-only policy).
#
#   bash scripts/fetch_upstream.sh                       # upstream/ + the G1 URDF at pinned revisions
#   docker build -t junction-sorter:dev .                 # build context = aalto-humanoid/
#   docker run --rm -p 8000:8000 junction-sorter:dev
#   python -m aaltonomous.deploy.replay --synthetic 100 --container junction-sorter:dev --gpus none
#
# Calibration (camera intrinsics/extrinsics) and config.yaml are baked in: rebuild after the organisers ship a new
# calibration version.
FROM nvidia/cuda:12.8.0-base-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip libgomp1 ca-certificates && rm -rf /var/lib/apt/lists/*
# Same pins as the organisers' baseline image (pin 3.3.1 = Pinocchio wheel, needs numpy >= 2.2)
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /app
COPY upstream/third_party/xr_teleoperate/assets/g1/g1_body29_hand14.urdf third_party/xr_teleoperate/assets/g1/
COPY upstream/aaltonomous/__init__.py aaltonomous/
COPY upstream/aaltonomous/deploy aaltonomous/deploy
COPY upstream/aaltonomous/interface aaltonomous/interface
COPY upstream/aaltonomous/scene aaltonomous/scene
COPY upstream/aaltonomous/baselines aaltonomous/baselines
# the oracle's planner class (pure numpy; sorter.planner.FacePlanner subclasses it) and the light layout module it imports
COPY upstream/aaltonomous/sim/oracle.py aaltonomous/sim/oracle.py
COPY upstream/aaltonomous/sim/aalto_task/__init__.py upstream/aaltonomous/sim/aalto_task/layout.py aaltonomous/sim/aalto_task/
COPY sorter sorter
# Load-time check at build: config, URDF, calibration and the parser load (fails the build, not the run).
RUN python3 -c "from sorter.server import SorterServerPolicy; p = SorterServerPolicy(); p.reset('Sort the objects: red into right, blue into left, yellow into center.', 'sort_language'); print(p.pol.full_mapping)"

EXPOSE 8000
CMD ["python3", "-m", "sorter.server"]
