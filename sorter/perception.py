"""Shape-aware perception: the organisers' HSV + depth detector, plus the shape of each object's top face.

The upstream detector (baselines/classical/perception.py) finds coloured blobs and the 3D centre of their top face.
This subclass also classifies the top face as cube / cylinder / triangle, from the same top-face points in the
pelvis frame (metric, so perspective does not distort it):

  rasterise the points on a 1 mm grid -> close gaps -> largest contour -> how well it fills its
  minimum-area rectangle (square ~1.0), its minimum enclosing circle (disc ~1.0) and its minimum enclosing
  triangle (triangle ~1.0); the best fill wins. Ideal values: square 1 / 0.64 / 0.5, disc 0.79 / 1 / 0.6,
  triangle 0.5 / 0.41 / 1.

Shape matters for (a) instructions that name shapes ("cubes go left"), (b) grasp choice: triangles slip in the
baseline's pinch, so the policy can grasp them along an edge (yaw from the enclosing triangle).
Blobs without enough depth (method "plane") get shape None.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np

from aaltonomous.baselines.classical.perception import Detection, Perception

GRID_M = 0.001
# ideal (rect fill, circle fill, triangle fill) per shape; the nearest signature wins (a disc fills 0.79 of its
# rectangle, so "largest fill" alone confuses discs with squares when the outline is noisy)
SIGNATURES = {"cube": np.array([1.0, 2 / np.pi, 0.5]),
              "cylinder": np.array([np.pi / 4, 1.0, np.pi / (3 * np.sqrt(3))]),
              "triangle": np.array([0.5, 3 * np.sqrt(3) / (4 * np.pi), 1.0])}


@dataclass(repr=False)
class ShapeDetection(Detection):
    shape: str | None = None
    shape_scores: dict | None = None
    shape_yaw: float | None = None          # triangle: direction centroid -> a vertex; square: edge direction
    top_stock: np.ndarray | None = None     # upstream top-face centre (kept when `top` is replaced by a fit)
    top_fit: np.ndarray | None = None       # cylinder: circle of the known radius fitted to all blob points

    def __repr__(self):
        return f"{super().__repr__()} shape={self.shape}"


def classify_top_face(xy: np.ndarray, grid=GRID_M):
    """xy (n, 2) metric points of a top face -> (shape | None, scores dict, yaw | None)."""
    import cv2
    if len(xy) < 30:
        return None, {}, None
    lo = xy.min(0) - 5 * grid
    ij = np.round((xy - lo) / grid).astype(int)
    h, w = ij.max(0) + 6
    if h > 400 or w > 400:                 # > 40 cm: not one object
        return None, {}, None
    img = np.zeros((int(w), int(h)), np.uint8)
    img[ij[:, 1], ij[:, 0]] = 255
    k = np.ones((5, 5), np.uint8)
    img = cv2.morphologyEx(img, cv2.MORPH_CLOSE, k)
    cs, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cs:
        return None, {}, None
    c = max(cs, key=cv2.contourArea)
    hull = cv2.convexHull(c)
    area = float(cv2.contourArea(hull))
    if area < 100:                         # < 1 cm^2
        return None, {}, None
    (_, _), (rw, rh), rang = cv2.minAreaRect(hull)
    (_, _), r = cv2.minEnclosingCircle(hull)
    tri_area, tri = cv2.minEnclosingTriangle(hull)
    scores = {"cube": area / max(rw * rh, 1e-9), "cylinder": area / max(np.pi * r * r, 1e-9),
              "triangle": area / max(float(tri_area), 1e-9)}
    s = np.array([scores["cube"], scores["cylinder"], scores["triangle"]])
    shape = min(SIGNATURES, key=lambda k: float(np.linalg.norm(s - SIGNATURES[k])))
    yaw = None
    if shape == "triangle" and tri is not None:
        v = tri.reshape(-1, 2).astype(float)
        cen = v.mean(0)
        d = v[0] - cen
        yaw = float(np.arctan2(d[1], d[0]))
    elif shape == "cube":
        a = np.radians(rang)
        yaw = float((a + np.pi / 4) % (np.pi / 2) - np.pi / 4)
    return shape, {k: round(float(s), 3) for k, s in scores.items()}, yaw


def fit_cylinder_center(P, z_top, r, band, c0):
    """xy centre of a vertical cylinder of radius r from its visible 3D points P (n, 3), pelvis frame.

    Side-face points (below the top band) lie ON the circle, top-face points inside it. When the lit top face drops
    out of the colour mask (washed-out saturation, brighter lighting), the stock top-band mean is the front face's
    upper edge, 15-20 mm short of the centre; the side arc still fixes the centre. Robust least squares from c0."""
    from scipy.optimize import least_squares
    side = P[P[:, 2] < z_top - band][:, :2]
    top = P[P[:, 2] >= z_top - band][:, :2]
    if len(side) < 20:
        return None
    side = side[:: max(1, len(side) // 400)]
    top = top[:: max(1, len(top) // 200)]

    def res(c):
        rs = np.linalg.norm(side - c, axis=1) - r
        rt = np.maximum(np.linalg.norm(top - c, axis=1) - r, 0.0) if len(top) else np.zeros(0)
        return np.concatenate([rs, rt])

    sol = least_squares(res, np.asarray(c0, float), loss="soft_l1", f_scale=0.003)
    c = sol.x
    if not sol.success or np.linalg.norm(c - c0) > 1.5 * r:
        return None
    return c


def auto_gain(rgb, target=220.0, pct=95, max_gain=3.0):
    """Brighten an under-exposed frame so its `pct` percentile brightness reaches `target` (never darkens).
    The HSV thresholds have value floors (50-90): a dim held-out lighting variant would otherwise lose objects."""
    v = np.asarray(rgb).max(axis=2)
    p = float(np.percentile(v, pct))
    if p <= 0 or p >= target:
        return rgb, 1.0
    g = min(target / p, max_gain)
    return np.clip(np.asarray(rgb, np.float32) * g, 0, 255).astype(np.uint8), g


# Real venue camera (Drop 3, 2026-11-14): red objects H 11-13 V ~250 (upstream red stops at H 8), orange-paper boxes
# H ~4 V ~120 (inside upstream red), yellow H ~42 (upstream stops at 35), the robot's dark hands H ~101 V 44-73 (inside
# upstream blue). The sim is the other way round for red (objects H 0-5, boxes H ~12), so hue alone cannot work for
# both: extend the hue ranges for BRIGHT pixels only and reject boxes by position and hands by brightness.
EXTRA_HSV = {"red": [[[8, 70, 170], [16, 255, 255]]], "yellow": [[[35, 60, 150], [50, 255, 255]]]}
REGION_MARGIN = 0.06       # m around the layout sampling region (calibration error, objects nudged by a grasp)
FAR_MARGIN = 0.05          # m past the box row's near edge (mat y) that still counts as an object position
GROSS_TILT_DEG = 4.0       # self-calibration "gross" mode: correct only beyond these (sim jitter is <= 1 deg / 1 cm)
GROSS_DZ = 0.02
MIN_BLOB_V = 100           # median HSV value of a blob (after auto gain); the real hands are 44-73, objects ~250


MERGE_RADIUS = 0.04        # m: same-colour detections closer than this are one object (top face + side face blobs)


def merge_duplicates(dets, radius=MERGE_RADIUS):
    """One detection per object: of same-colour detections within `radius` (xy), keep the highest top (the top face;
    a side-face blob of the same object sits lower). Real venue frames split bright tops from shaded sides."""
    keep = []
    for d in sorted(dets, key=lambda d: -float(d.top[2])):
        if any(k.color == d.color and np.linalg.norm(k.top[:2] - d.top[:2]) < radius for k in keep):
            continue
        keep.append(d)
    return keep


class ShapePerception(Perception):
    def __init__(self, cfg, scene, calibration):
        super().__init__(cfg, scene, calibration)
        self.extra_hsv = self.cfg.get("extra_hsv", EXTRA_HSV)
        self.region_margin = float(self.cfg.get("region_margin", REGION_MARGIN))
        self.min_blob_v = float(self.cfg.get("min_blob_v", MIN_BLOB_V))
        self.far_margin = float(self.cfg.get("far_margin", FAR_MARGIN))
        self._v = None
        self._depth_frac = 0.0
        # per-frame head extrinsics correction (sorter.selfcal). SORTER_SELFCAL:
        #   gross (default) = counter-plane correction only, and only when the nominal calibration is clearly wrong
        #     (tilt >= GROSS_TILT_DEG or height off >= GROSS_DZ): the real Drop 3 frames (~14 deg, ~3 cm) trigger it,
        #     the sim's +-1 deg / +-1 cm jitter never does (so sim behaviour = no correction);
        #   full = plane + box-rim fit every frame (sim diagnostic 2026-11-15: mixed, one scene lost every object);
        #   off = nominal calibration.
        self.selfcal_mode = os.environ.get("SORTER_SELFCAL", "gross")
        self.selfcal_on = self.selfcal_mode != "off"
        self.T0 = self.cal.cams[self.cam].T_pelvis_optical.copy()
        self.last_selfcal = None

    def masks(self, rgb):
        import cv2
        rgb, self.last_gain = auto_gain(rgb)
        out = super().masks(rgb)
        hsv = cv2.cvtColor(np.ascontiguousarray(rgb), cv2.COLOR_RGB2HSV)
        self._v = hsv[..., 2]
        k = int(self.cfg["open_px"])
        for color, ranges in (self.extra_hsv or {}).items():
            if color not in out:
                continue
            m = np.zeros(hsv.shape[:2], np.uint8)
            for lo, hi in ranges:
                m |= cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
            if k > 0:
                m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
            out[color] = out[color] | m
        return out

    def detect(self, rgb, depth, debug=False):
        if depth is not None:
            dlo, dhi = self.cfg["depth_range_mm"]
            self._depth_frac = float(((depth >= dlo) & (depth <= dhi)).mean())
        else:
            self._depth_frac = 0.0
        if self.selfcal_on:
            self._selfcalibrate(depth)
        out = super().detect(rgb, depth, debug=debug)
        dets, rej = out if debug else (out, None)
        dets = merge_duplicates(dets, self.cfg.get("merge_radius", MERGE_RADIUS))
        return (dets, rej) if debug else dets

    def _selfcalibrate(self, depth, step=3):
        """Set this frame's head extrinsics to C @ T0 (sorter.selfcal); keep the last good C when a frame fails."""
        from . import selfcal
        cam = self.cal.cams[self.cam]
        if depth is None or self._depth_frac < 0.3:
            return
        dlo, dhi = self.cfg["depth_range_mm"]
        v, u = np.mgrid[0:depth.shape[0]:step, 0:depth.shape[1]:step]
        d = depth[v, u].astype(float)
        ok = (d >= dlo) & (d <= dhi)
        cam.T_pelvis_optical = self.T0.copy()
        P = self.cal.pixel_to_pelvis(self.cam, u[ok], v[ok], d[ok])
        try:
            est = selfcal.estimate(P, self.scene, boxes=self.selfcal_mode == "full")
        except Exception:            # never let calibration break a look
            est = None
        if est is not None and self.selfcal_mode != "full":
            gross = est.plane_ok and (est.info.get("plane_tilt_deg", 0.0) >= GROSS_TILT_DEG
                                      or abs(est.info.get("plane_dz", 0.0)) >= GROSS_DZ)
            if not gross:
                est = None
        if est is not None and (est.plane_ok or est.bins_ok):
            self.last_selfcal = est
        if self.last_selfcal is not None:
            cam.T_pelvis_optical = self.last_selfcal.C @ self.T0

    def _blob_v(self, u, v):
        if self._v is None or len(u) == 0:
            return None
        return float(np.median(self._v[np.asarray(v, int), np.asarray(u, int)]))

    def _from_plane(self, color, uv, area, n_depth):
        det = super()._from_plane(color, uv, area, n_depth)
        if det is not None and self._v is not None:
            u0, v0 = int(round(uv[0])), int(round(uv[1]))
            patch = self._v[max(v0 - 3, 0):v0 + 4, max(u0 - 3, 0):u0 + 4]
            det.v_med = float(np.median(patch)) if patch.size else None
        return det

    def _reject(self, det):
        why = super()._reject(det)
        if why:
            return why
        vm = getattr(det, "v_med", None)
        if vm is not None and vm < self.min_blob_v:
            return f"dark {vm:.0f}"
        if det.method == "plane" and self._depth_frac >= 0.5:
            return "no depth on a depth frame"     # real objects have depth (Drop 3); these are robot parts / glare
        L, sc = self.scene.cfg["layout"], self.scene
        pm = sc.pelvis_to_mat(det.top)
        m = self.region_margin
        # far side: up to the box row's near edge + FAR_MARGIN (real layouts reach the boxes; the orange flaps
        # between the boxes measured at pelvis x >= 0.49 on the venue frames)
        far = self._box_near_y() + self.far_margin
        if not (L["region_x"][0] - m <= pm[0] <= L["region_x"][1] + m and L["region_y"][0] - m <= pm[1] <= far):
            return "off_region"
        return None

    def _box_near_y(self):
        b = self.scene.cfg["bins"]
        return min(float(c[1]) for c in b["centers"].values()) - float(b["outer_size"][1]) / 2

    def _from_depth(self, color, u, v, d, area):
        det = super()._from_depth(color, u, v, d, area)
        if det is None:
            return None
        P = self.cal.pixel_to_pelvis(self.cam, u, v, d)
        z_top = np.percentile(P[:, 2], self.cfg["top_percentile"])
        top = P[P[:, 2] >= z_top - self.cfg["top_band"]]
        shape, scores, yaw = classify_top_face(top[:, :2])
        top_fit = None
        if shape == "cylinder":
            r = 0.5 * float(self.scene.cfg["objects"].get("size", 0.045))
            c = fit_cylinder_center(P, z_top, r, self.cfg["top_band"], det.top[:2] - self.xy_offset)
            if c is not None:
                top_fit = np.array([c[0] + self.xy_offset[0], c[1] + self.xy_offset[1], det.top[2]])
        out = ShapeDetection(det.color, det.top, det.n_px, det.n_depth, det.method, det.yaw, det.uv,
                             shape=shape, shape_scores=scores, shape_yaw=yaw, top_stock=det.top.copy(), top_fit=top_fit)
        out.v_med = self._blob_v(u, v)
        if top_fit is not None and os.environ.get("SORTER_CENTER", "stock") == "fit":
            out.top = top_fit
        return out
