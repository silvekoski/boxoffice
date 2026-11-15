"""Per-frame head-camera self-calibration from the scene's fixed geometry (counter plane + the three boxes).

Why: the sim's domain randomisation jitters the head extrinsics by +-1 cm / +-1 deg (aaltonomous/sim/dr/train.yaml,
"head extrinsic error", also in the held-out variant), which moves every detection by the same 5-30 mm in a scene
(sim/perception_diag.py, 2026-11-15: median 12-13 mm, p90 ~24 mm on 82 objects). A pinch on a 45 mm object slips at
that error, cylinders first. On the real robot the provisional calibration is worse (Drop 3 frames: object tops read
60-87 mm for 45 mm objects). The counter and the boxes are fixed and known, so the frame itself says where the
camera is.

Method, in the pelvis frame with the nominal extrinsics T:
  1. counter plane: RANSAC plane through depth points near the counter height (mat area, outside the boxes);
     the rotation that levels it + the height offset fix pitch, roll and z;
  2. boxes: points at rim height (counter + 0.5..1.15 wall heights) near the known box outlines; a robust 2D rigid
     fit (dx, dy, yaw about the box row centre) of those points to the outer box rectangles fixes x, y, yaw.
The correction C (4x4, pelvis frame) gives the corrected extrinsics C @ T. Each step is bounded (2 cm / 2.5 deg)
and needs enough inliers; otherwise that step is skipped (identity), so a bad frame cannot make things worse
than the nominal calibration by more than the bound.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# Bounds. Sim DR jitter is +-1 cm / +-1 deg; the real Drop 3 frames show the counter tilted ~12 deg and 3-4 cm high
# under calibration v1 (same in all 15 episodes), so the plane step allows large corrections; the box step after it
# only fine-tunes.
MAX_TILT = np.radians(20.0)
MAX_DZ = 0.08
MAX_SHIFT = 0.04           # m, box step
MAX_ANGLE = np.radians(5.0)  # box step yaw


@dataclass
class SelfCal:
    C: np.ndarray = field(default_factory=lambda: np.eye(4))
    plane_ok: bool = False
    bins_ok: bool = False
    n_plane: int = 0
    n_rim: int = 0
    info: dict = field(default_factory=dict)


def _rot(axis_angle):
    v = np.asarray(axis_angle, float)
    th = np.linalg.norm(v)
    if th < 1e-12:
        return np.eye(3)
    k = v / th
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(th) * K + (1 - np.cos(th)) * K @ K


def _apply(C, P):
    return P @ C[:3, :3].T + C[:3, 3]


def fit_plane_ransac(P, rng, iters=200, tol=0.004):
    """Plane n.p = d through P (n, 3) with n_z > 0; returns (n, d, inlier mask) or None."""
    if len(P) < 50:
        return None
    best, best_in = None, None
    for _ in range(iters):
        s = P[rng.choice(len(P), 3, replace=False)]
        n = np.cross(s[1] - s[0], s[2] - s[0])
        if np.linalg.norm(n) < 1e-9:
            continue
        n /= np.linalg.norm(n)
        if n[2] < 0:
            n = -n
        if n[2] < np.cos(MAX_TILT):
            continue
        inl = np.abs(P @ n - n @ s[0]) < tol
        if best_in is None or inl.sum() > best_in.sum():
            best, best_in = (n, float(n @ s[0])), inl
    if best is None:
        return None
    Q = P[best_in]                                  # least-squares refit on the inliers
    c = Q.mean(0)
    _, _, vt = np.linalg.svd(Q - c)
    n = vt[2] if vt[2][2] > 0 else -vt[2]
    return n, float(n @ c), best_in


def box_rects(scene):
    """Outer rectangles of the boxes in the pelvis frame: list of (centre xy (2,), half sizes (2,))."""
    b = scene.cfg["bins"]
    half = np.asarray(b["outer_size"], float) / 2
    out = []
    for c in b["centers"].values():
        p = scene.mat_to_pelvis([float(c[0]), float(c[1]), 0.0])
        # mat x -> pelvis y, mat y -> pelvis x (scene.yaml): swap the half sizes
        out.append((np.array([p[0], p[1]]), np.array([half[1], half[0]])))
    return out


def rect_dist(xy, centre, half):
    """Unsigned distance of points (n, 2) to the boundary of an axis-aligned rectangle."""
    d = np.abs(xy - centre) - half
    outside = np.linalg.norm(np.maximum(d, 0.0), axis=1)
    inside = np.minimum(np.max(d, axis=1), 0.0)
    return np.where(outside > 0, outside, -inside)


def estimate(P, scene, rng=None, counter_band=0.12, boxes=True):
    """P: (n, 3) pelvis-frame points from the nominal extrinsics (valid depth). Returns SelfCal."""
    from scipy.optimize import least_squares
    rng = rng or np.random.default_rng(0)
    out = SelfCal()
    zc = float(scene.counter_z)
    wall = float(scene.cfg["bins"]["wall_height"])
    rects = box_rects(scene)
    near_box = np.zeros(len(P), bool)
    for c, h in rects:
        near_box |= np.all(np.abs(P[:, :2] - c) <= h + 0.03, axis=1)

    # 1. counter plane (mat area in front of the boxes, not on them)
    L = scene.cfg["layout"]
    pm = scene.pelvis_to_mat(P)
    in_mat = (pm[:, 0] > L["region_x"][0] - 0.12) & (pm[:, 0] < L["region_x"][1] + 0.12) \
        & (pm[:, 1] > 0.0) & (pm[:, 1] < L["region_y"][1] + 0.08)
    cand = P[in_mat & ~near_box & (P[:, 2] > zc - counter_band) & (P[:, 2] < zc + counter_band)]
    if len(cand) > 4000:
        cand = cand[rng.choice(len(cand), 4000, replace=False)]
    C1 = np.eye(4)
    fit = fit_plane_ransac(cand, rng, iters=300)
    if fit is not None and fit[2].sum() >= 300:
        n, d, inl = fit
        axis = np.cross(n, [0.0, 0.0, 1.0])
        ang = float(np.arcsin(np.clip(np.linalg.norm(axis), -1, 1)))
        if ang <= MAX_TILT:
            R = _rot(axis / max(np.linalg.norm(axis), 1e-12) * ang) if ang > 1e-9 else np.eye(3)
            c = cand[inl].mean(0)
            C1[:3, :3] = R
            C1[:3, 3] = c - R @ c                     # rotate about the inlier centroid
            dz = zc - float((R @ c)[2] + C1[2, 3])
            if abs(dz) <= MAX_DZ:
                C1[2, 3] += dz
                out.plane_ok, out.n_plane = True, int(inl.sum())
                out.info.update(plane_tilt_deg=float(np.degrees(ang)), plane_dz=float(dz))
    P1 = _apply(C1, P) if out.plane_ok else P

    # 2. box rims: 2D rigid fit to the outer rectangles
    zr = P1[:, 2] - zc
    near1 = np.zeros(len(P1), bool)
    for c, h in rects:
        near1 |= np.all(np.abs(P1[:, :2] - c) <= h + 0.03, axis=1) & ~np.all(np.abs(P1[:, :2] - c) <= h - 0.03, axis=1)
    rim = P1[near1 & (zr > 0.5 * wall) & (zr < 1.15 * wall + 0.01)][:, :2]
    if len(rim) > 3000:
        rim = rim[rng.choice(len(rim), 3000, replace=False)]
    C2 = np.eye(4)
    if boxes and len(rim) >= 200:
        pivot = np.mean([c for c, _ in rects], axis=0)

        def res(x):
            th, t = x[0], x[1:3]
            R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
            q = (rim - pivot) @ R.T + pivot + t
            return np.min(np.stack([rect_dist(q, c, h) for c, h in rects]), axis=0)

        r0 = res(np.zeros(3))
        sol = least_squares(res, np.zeros(3), loss="soft_l1", f_scale=0.004,
                            bounds=([-MAX_ANGLE, -MAX_SHIFT, -MAX_SHIFT], [MAX_ANGLE, MAX_SHIFT, MAX_SHIFT]))
        r1 = res(sol.x)
        inl = float(np.mean(np.abs(r1) < 0.006))
        if sol.success and inl >= 0.5 and np.median(np.abs(r1)) <= np.median(np.abs(r0)):
            th, t = sol.x[0], sol.x[1:3]
            R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
            C2[:2, :2] = R
            C2[:2, 3] = pivot - R @ pivot + t
            out.bins_ok, out.n_rim = True, len(rim)
            out.info.update(bins_dxy_mm=[float(1000 * t[0]), float(1000 * t[1])], bins_yaw_deg=float(np.degrees(th)),
                            rim_inliers=inl, rim_med_mm_before=float(1000 * np.median(np.abs(r0))),
                            rim_med_mm_after=float(1000 * np.median(np.abs(r1))))
    out.C = C2 @ C1
    return out
