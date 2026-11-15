"""Grasp planners on top of the organisers' stack.

FacePlanner (default since 2026-11-15) is the organisers' oracle planner (`aaltonomous.sim.oracle._OraclePlanner`)
driven by OUR camera detections. Nothing in that class is privileged: only the oracle's detections come from the
sim state. Over the classical planner it adds
  * face-aligned grasps for cubes and triangular prisms: fingers along a face normal (cube) or at the grasp-tested
    105 deg from the apex (prism, `AALTO_TRI_PHI`), IK finger-direction weight 3.0, the achieved finger direction
    checked within 12 deg, and the prism's pinch midpoint corrected (support function, not the centroid),
  * a joint-space carry and Cartesian segments shortened to one joint move when the hand stays on the line
    (~3x shorter joint paths at the same speed limit: faster picks, more time for retries),
  * bin margin 0 (objects close to the centre bin wall are reachable with fingers forward),
  * a cached "can this arm reach that bin at all" reject before the slow cross-body carry search,
  * drop offsets inside a bin, so the next object does not land on the previous one.
In the 2026-11-15 randomised-scene run with ShapePlanner, every miss was a grasp that slipped (cylinder 13/34,
prism 8/29, cube 21/28); the oracle with this planner sorted 21/23 objects on the nominal scene.

Yaw conventions: ShapeDetection.shape_yaw is centroid -> a vertex (prism) or an edge direction (cube, mod 90 deg).
The oracle's `yaw` is the mesh yaw: prism apex along mesh +y, so apex direction = yaw + 90 deg; cube face normals
at yaw + k * 90 deg. Hence oracle yaw = shape_yaw - 90 deg (prism), = shape_yaw (cube).

ShapePlanner (`SORTER_PLANNER=shape`) is the previous planner: classical finger hints, prism fingers on a face.
"""
from __future__ import annotations

import copy

import numpy as np

from aaltonomous.baselines.classical.planner import Planner
import aaltonomous.sim.oracle as _oracle
from aaltonomous.sim.oracle import DROP_OFFSETS, _OraclePlanner

# Face directions: the oracle's 75 deg. A 45 deg limit (faster planning) was tried in v7/v8 and lost prisms in the sim
# (sort_language 7/11 -> 4/11 on the same scenes, mostly prisms left on the counter), so it is not used.

__all__ = ["FacePlanner", "ShapePlanner", "aligned_direction", "oracle_yaw", "DROP_OFFSETS"]


def oracle_yaw(shape, shape_yaw):
    """ShapeDetection.shape_yaw -> the oracle planner's object yaw (see module docstring), or None."""
    if shape_yaw is None:
        return None
    if shape == "triangle":
        return float(shape_yaw - np.pi / 2)
    if shape == "cube":
        return float(shape_yaw)
    return None


class FacePlanner(_OraclePlanner):
    """The oracle's planner with yaw taken from our perception. drop_offsets: bin -> (dx, dy), set by the policy."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.drop_offsets = {}

    def _plan_side_faces(self, det, side, bin_name, arm_q, hand_q, **kw):
        shape = getattr(det, "shape", None)
        d2 = copy.copy(det)
        d2.yaw = oracle_yaw(shape, getattr(det, "shape_yaw", None))   # None -> stock finger hints
        p = super()._plan_side_faces(d2, side, bin_name, arm_q, hand_q, **kw)
        if p.ok and shape == "cylinder":
            p.reason = (p.reason + "; " if p.reason else "") + "cylinder"
        return p


def aligned_direction(shape, yaw, mode="face", forward=(1.0, 0.0)):
    """Pelvis-frame unit xy direction for the fingers, or None. yaw: triangle = centroid -> vertex, cube = an edge."""
    if yaw is None or shape not in ("triangle", "cube") or not mode:
        return None
    if shape == "triangle":
        base = yaw + (np.pi if mode == "face" else 0.0)       # fingers towards a face = against a vertex direction
        cands = base + 2 * np.pi * np.arange(3) / 3
    else:
        cands = yaw + np.pi / 2 * np.arange(4)                # face normals of a square
    f = np.asarray(forward, float)
    dirs = np.stack([np.cos(cands), np.sin(cands)], -1)
    return dirs[int(np.argmax(dirs @ f))]


class ShapePlanner(Planner):
    """Previous planner (until 2026-11-15): stock finger hints; prisms first with the fingers on a face."""

    def _plan_side_hints(self, det, side, bin_name, arm_q, hand_q, **kw):
        g = self.cfg["grasp"]
        mode = g.get("triangle_align", "face")
        shape = getattr(det, "shape", None)
        d = None
        if shape in g.get("align_shapes", ("triangle",)):     # cubes already work with the fixed hints (FAQ)
            d = aligned_direction(shape, getattr(det, "shape_yaw", None), mode)
        if d is None:
            return super()._plan_side_hints(det, side, bin_name, arm_q, hand_q, **kw)
        saved_hint = self.kin.hint
        h = np.array([d[0], d[1], 0.0])
        try:
            self.kin.hint = h
            p = self._plan_side(det, side, bin_name, arm_q, hand_q, **kw)
        finally:
            self.kin.hint = saved_hint
        if p.ok:
            p.reason = (p.reason + "; " if p.reason else "") + f"{det.shape}-aligned grasp"
            return p
        return super()._plan_side_hints(det, side, bin_name, arm_q, hand_q, **kw)
