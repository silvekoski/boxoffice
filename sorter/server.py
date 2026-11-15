"""Our submission: SortingPolicy behind the organisers' policy-server protocol (websocket + msgpack, port 8000).

    python -m sorter.server                     # what the Docker image runs (PORT env to change)

Threaded like the reference submission: look + plan (IK) runs in a background thread while act() returns hold
chunks at once, so the command rate stays ~30 Hz; motion comes back in `motion.chunk`-tick chunks.
Env: AALTO_TIME_LIMIT (s, default 120), AALTO_ARM_VEL (rad/s override), AALTO_PROFILE (config profile, default sim).
"""
from __future__ import annotations

import logging
import os
import time

import numpy as np

from aaltonomous.deploy.policy_server import Policy, serve

from .policy import SortingPolicy

log = logging.getLogger("sorter")


class SorterServerPolicy(Policy):
    name = "junction-sorter"

    def __init__(self, time_limit=None, arm_vel=None, **kw):
        tl = float(time_limit or os.environ.get("AALTO_TIME_LIMIT", 120.0))
        ov = {}
        av = arm_vel or os.environ.get("AALTO_ARM_VEL")
        if av:
            ov["motion.arm_max_vel"] = float(av)
        self.pol = SortingPolicy(threaded=True, require_confirm=False, time_limit=tl, overrides=ov,
                                 log=lambda m: log.info(m), **kw)
        self.action_horizon = int(self.pol.cfg["motion"]["chunk"])

    def reset(self, instruction, task=None, seed=None):
        # an episode can end mid-look: let that planning thread finish first (planner state is not thread-safe)
        job, t0 = self.pol._job, time.monotonic()
        while job is not None and job["result"] is None and time.monotonic() - t0 < 30.0:
            time.sleep(0.02)
        self.pol.reset({"instruction": instruction, "task": task})
        log.info("reset task=%s seed=%s", task, seed)

    def act(self, obs):
        a = self.pol.act(obs)
        return {"arm_q_target": np.asarray(a["arm_q_target"], np.float64),
                "hand_q_target": np.asarray(a["hand_q_target"], np.float64), "done": bool(a.get("done", False))}


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    t0 = time.monotonic()
    pol = SorterServerPolicy()
    log.info("sorter loaded in %.1f s", time.monotonic() - t0)
    serve(pol, port=int(os.environ.get("PORT", 8000)))


if __name__ == "__main__":
    main()
