"""Offline planner benchmark (no sim): random object poses on the mat, every shape, plan from home to the bin the
fixed rule gives; reports plannable fraction, pick duration and safety clips per planner and shape.

    PYTHONPATH=.:upstream .venv/bin/python scripts/bench_planner.py [n=120]
"""
import os
import sys
import time

import numpy as np


def run(kind, n, seed=0):
    os.environ["SORTER_PLANNER"] = kind
    from sorter.perception import ShapeDetection
    from sorter.policy import SortingPolicy
    pol = SortingPolicy(log=None)
    pol.reset({"instruction": "", "task": "sort_fixed"})
    sc = pol.scene
    L = sc.cfg["layout"]
    rng = np.random.default_rng(seed)
    arm, hand = pol.home.copy(), pol.post["open"].copy()
    rows = []
    for i in range(n):
        shape = ("cube", "cylinder", "triangle")[i % 3]
        color = ("red", "yellow", "blue")[(i // 3) % 3]
        mx = rng.uniform(*L["region_x"]); my = rng.uniform(*L["region_y"])
        p = sc.mat_to_pelvis([mx, my, 0.0])
        top = np.array([p[0], p[1], sc.counter_z + sc.object_height(shape)])
        yaw = rng.uniform(-np.pi, np.pi)
        det = ShapeDetection(color, top, 500, 400, "depth", shape=shape, shape_yaw=None if shape == "cylinder" else yaw)
        bin_name = pol.full_mapping.get(color)
        t0 = time.monotonic()
        plan = pol.planner.plan(det, arm, hand, bin_name=bin_name)
        rows.append((shape, plan.ok, plan.duration if plan.ok else np.nan, plan.safety_clips if plan.ok else 0,
                     time.monotonic() - t0, plan.reason or ""))
    return rows


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    kind = sys.argv[2] if len(sys.argv) > 2 else None
    for k in ([kind] if kind else ["shape", "face"]):
        rows = run(k, n)
        print(f"== {k}")
        for shape in ("cube", "cylinder", "triangle", None):
            R = [r for r in rows if shape is None or r[0] == shape]
            ok = [r for r in R if r[1]]
            face = sum("face-aligned" in r[5] or "aligned grasp" in r[5] for r in ok)
            print(f"  {shape or 'all':9s} plannable {len(ok)}/{len(R)}  pick {np.nanmean([r[2] for r in ok]):5.1f} s"
                  f"  plan time {np.mean([r[4] for r in R]):4.1f} s  clips {sum(r[3] for r in ok)}  aligned {face}"
                  f"  relocations {sum('relocate' in r[5] for r in ok)}")
