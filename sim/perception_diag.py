"""Perception error against the sim's ground truth on randomised scenes (no policy, no full episodes).

For each seed: arms home, DR `randomize`, a new layout, hold ~1 s, one head RGB-D frame -> ShapePerception
(what our image runs) -> match each detection to the true object (scene service state) -> xy error, shape and
colour correctness, misses and false positives. ~10 s per seed instead of 5-15 min per scored trial.

    # on the VM, sim running (AALTO_DR=train aalto sim), from /root/work/upstream:
    PYTHONPATH=/root/work/aalto-humanoid:$PWD python /root/work/aalto-humanoid/sim/perception_diag.py \
        --seeds 1000:1040 --out /root/work/diag
Instance env vars (AALTO_INSTANCE, AALTO_*_PORT) work as for evaluate.py. Writes diag.json, frames/<seed>_*.png
and prints a table per shape plus the mean xy error vs lighting.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1000:1020")
    ap.add_argument("--out", default="/root/work/diag")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--hold-s", type=float, default=1.0)
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.seeds.split(":"))
    out = Path(a.out); (out / "frames").mkdir(parents=True, exist_ok=True)

    import cv2
    from aaltonomous.interface.env import AaltoEnv
    from aaltonomous.sim.evaluate import apply_instance_env, home_arms
    from aaltonomous.sim.scene_client import SceneClient
    from sorter.policy import SortingPolicy

    apply_instance_env()
    sc = SceneClient(a.host)
    import os
    env = AaltoEnv(backend="sim", task="sort_fixed", seed=lo, time_limit=30.0, realtime=True, img_server_ip=a.host,
                   head_rgbd=True, head_rgbd_port=int(os.environ.get("AALTO_RGBD_PORT", "55560")), cameras=True)
    pol = SortingPolicy(log=None)
    per = pol.perception
    rows = []
    for seed in range(lo, hi):
        home_arms(env, sc)
        env.rng = np.random.default_rng(seed)
        dr = sc.call(cmd="randomize", seed=seed).get("params")
        obs = env.reset()
        hold = {"arm_q_target": obs["arm_q"], "hand_q_target": obs["hand_q"]}
        for _ in range(int(a.hold_s * 30)):
            obs, *_ = env.step(hold)
        rgb, depth = obs.get("head_rgb"), obs.get("head_depth")
        for _ in range(60):                       # wait for a real frame (the camera stream can lag the reset)
            if rgb is not None and float(np.asarray(rgb).mean()) > 10:
                break
            obs, *_ = env.step(hold)
            rgb, depth = obs.get("head_rgb"), obs.get("head_depth")
        if rgb is None or float(np.asarray(rgb).mean()) <= 10:
            print(f"seed {seed}: head camera blank, skipped", flush=True)
            continue
        dets = per.detect(rgb, depth)
        truth = [o for o in sc.state()["objects"] if o["active"]]
        cv2.imwrite(str(out / "frames" / f"{seed}_rgb.png"), cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2BGR))
        used = set()
        for o in truth:
            p = np.asarray(o["pos"], float)
            best, bd = None, 1e9
            for j, d in enumerate(dets):
                if j in used:
                    continue
                e = float(np.linalg.norm(d.top[:2] - p[:2]))
                if e < bd:
                    best, bd = j, e
            r = {"seed": seed, "name": o["name"], "shape": o["shape"], "color": o["color"],
                 "x": float(p[0]), "y": float(p[1]), "found": best is not None and bd < 0.04}
            if r["found"]:
                used.add(best)
                d = dets[best]
                err = d.top[:2] - p[:2]
                st = getattr(d, "top_stock", None); ft = getattr(d, "top_fit", None)
                if st is not None:
                    r["err_stock"] = float(np.linalg.norm(st[:2] - p[:2]))
                if ft is not None:
                    r["err_fit"] = float(np.linalg.norm(ft[:2] - p[:2]))
                r.update(err_x=float(err[0]), err_y=float(err[1]), err=bd, det_shape=d.shape, det_color=d.color,
                         method=d.method, n_px=int(d.n_px), shape_ok=d.shape == o["shape"], color_ok=d.color == o["color"])
            rows.append(r)
        fp = len(dets) - len(used)
        light = (dr or {}).get("lighting", {})
        rows.append({"seed": seed, "false_positives": fp, "key": light.get("key_intensity_scale"),
                     "dome": light.get("dome_intensity_scale")})
        objs = [r for r in rows if r.get("seed") == seed and "name" in r]
        print(f"seed {seed}: {sum(r['found'] for r in objs)}/{len(objs)} found, fp {fp}, "
              + ", ".join(f"{r['color'][0]}{r['shape'][:3]} {1000 * r.get('err', np.nan):.0f}mm" for r in objs), flush=True)
    env.close()
    (out / "diag.json").write_text(json.dumps(rows, indent=1))
    objs = [r for r in rows if "name" in r]
    print("\nshape      found   xy err median / p90 (mm)   err_x mean (mm)   shape ok   colour ok")
    for s in ("cube", "cylinder", "triangle"):
        R = [r for r in objs if r["shape"] == s]
        F = [r for r in R if r["found"]]
        if not R:
            continue
        e = np.array([r["err"] for r in F]) * 1000 if F else np.array([np.nan])
        ex = np.mean([r["err_x"] for r in F]) * 1000 if F else np.nan
        print(f"{s:9s} {len(F):3d}/{len(R):<3d}   {np.median(e):6.1f} / {np.percentile(e, 90):6.1f}"
              f"            {ex:+6.1f}        {sum(r['shape_ok'] for r in F):3d}/{len(F):<3d}   "
              f"{sum(r['color_ok'] for r in F):3d}/{len(F)}")
    C = [r for r in objs if "err_fit" in r and "err_stock" in r]
    if C:
        print(f"cylinder centre, {len(C)} with a fit: stock median {1000 * np.median([r['err_stock'] for r in C]):.1f} mm"
              f" / p90 {1000 * np.percentile([r['err_stock'] for r in C], 90):.1f};  fit median "
              f"{1000 * np.median([r['err_fit'] for r in C]):.1f} mm / p90 {1000 * np.percentile([r['err_fit'] for r in C], 90):.1f}")
    print(f"false positives: {sum(r.get('false_positives', 0) for r in rows)}")


if __name__ == "__main__":
    main()
