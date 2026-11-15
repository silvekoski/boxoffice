"""SortingPolicy: the organisers' classical pick-and-place state machine, with our instruction parser, shape-aware
perception and a few robustness fixes.

What changes against baselines/classical/policy.py (everything else, incl. the planner's safety pre-check, is reused):
  * reset() parses the free-text instruction (sorter.instruction) into a mapping with colour / shape /
    (colour, shape) / "default" keys; each detection's bin is resolved with the scorer's own resolve_bin().
  * perception is ShapePerception (top-face shape per object).
  * a blank head frame (camera not streaming yet) is looked at again instead of ending the episode with
    "nothing left to sort"; an empty look must be confirmed by a second look before the policy says done.
  * objects whose bin the instruction does not decide are skipped (0 points) instead of guessed (EV <= 0).
  * planner: FacePlanner (the organisers' oracle planner on our detections: face-aligned cube / prism grasps,
    shorter joint paths, drop offsets inside the bins); SORTER_PLANNER=shape selects the previous ShapePlanner.
  * optional, online only (NVIDIA_API_KEY set): on the first frame with objects, Nemotron 3.5 Super VL reads the
    head image, our detections and the instruction and returns a validated sort plan (sorter.nemotron) that
    replaces the parser mapping; any failure keeps the parser mapping. Off in the finals (no network, no key).
"""
from __future__ import annotations

import os

import numpy as np

from aaltonomous.baselines.classical.policy import HZ, ClassicalPolicy
from aaltonomous.scene.scene import resolve_bin

from . import nemotron
from .instruction import FIXED_MAPPING, parse_instruction
from .perception import ShapePerception
from .planner import DROP_OFFSETS, FacePlanner, ShapePlanner

MAX_BLANK_LOOKS = 60          # ~ 60 x hold_ticks/30 s of waiting for the first camera frame
EMPTY_LOOKS_TO_FINISH = 2
MIN_FRAME_MEAN = 3.0          # head frames darker than this (0-255 mean) count as blank
# Extra attempts are OFF (= the config's 2): the v7 sim run (2026-11-15) showed one slipping object grasped 7 times in
# an episode (each slip nudges it 1-2 cm, so attempts near its new position started from zero) while the others
# waited; sort_language fell from 7/11 to 4/11 on the same scenes. Attempts are now also counted per colour across
# ATTEMPT_DRIFT_M, so a nudged object keeps its count.
EXTRA_ATTEMPTS_MAX = 2
ATTEMPT_DRIFT_M = 0.06
EXTRA_ATTEMPTS_RESERVE_S = 30.0
NEAR_BOX_M = 0.06             # objects this close to the box row are planned last (see SortingPolicy._order_key)


# Perception limits from the real venue frames (tests/test_real_frames.py): real objects are 900-3500 px at the head
# camera's distance, the robot wrist shows up as ~120 px specks; table glare sits at ~0.4 object heights, a standing
# object's top at 1.0 and a tipped prism at ~0.87.
# bin_exclusion_margin -0.015: a detection counts as "already in a box" only when its centre is 1.5 cm inside the box
# footprint (sorted objects are well inside; box-wall pixels are masked before grouping), so objects that touch the
# box row's front survive a residual calibration error (real ep02 prism: 1 mm inside the footprint at +0.01).
PERCEPTION_OVERRIDES = {"perception.min_area_px": 250, "perception.height_range": [0.6, 2.0]}
# (bin_exclusion_margin -0.015 was tried in v5-v8; not sim-validated, back to the upstream 0.01)

# The oracle's release posture (= preshape: thumb back + up), with FacePlanner; the rest of ORACLE_OVERRIDES is
# already in the classical config's `sim` profile.
FACE_OVERRIDES = {"hand.open": [0.0, -0.5, 1.5, -0.4, -0.4, -0.4, -0.4]}


class SortingPolicy(ClassicalPolicy):
    def __init__(self, *a, **kw):
        self.planner_kind = os.environ.get("SORTER_PLANNER", "face")
        if not isinstance(kw.get("config"), dict):
            base = {**PERCEPTION_OVERRIDES, **(FACE_OVERRIDES if self.planner_kind == "face" else {})}
            kw["overrides"] = {**base, **(kw.get("overrides") or {})}
        super().__init__(*a, **kw)
        self.perception = ShapePerception(self.cfg, self.scene, self.cal)
        if self.planner_kind == "face":
            self.planner = FacePlanner(self.cfg, self.scene, self.post, self.home, self.kin, self.safety, self.spec)
        else:
            # SORTER_TRIANGLE_ALIGN=face|vertex|off (A/B in sim); default face
            mode = os.environ.get("SORTER_TRIANGLE_ALIGN", self.cfg["grasp"].get("triangle_align", "face"))
            self.cfg["grasp"]["triangle_align"] = None if mode in ("off", "none", "") else mode
            self.planner = ShapePlanner(self.cfg, self.scene, self.post, self.home, self.kin, self.safety, self.spec)
        self.planner.mapping = self.mapping
        self.drops = {}

    def reset(self, info=None):
        if isinstance(info, str):
            info = {"instruction": info}
        info = dict(info or {})
        self.parse = parse_instruction(info.get("instruction", ""), task=info.get("task"))
        colour_view = {c: b for c, b in self.parse.color_mapping().items() if b is not None}
        info["mapping"] = colour_view or dict(FIXED_MAPPING)
        super().reset(info)
        self.drops = {}                       # bin -> objects released there this episode (drop offsets)
        self._attempt_colors = []
        self.full_mapping = dict(self.parse.mapping)
        self._blank_looks = 0
        self._empty_looks = 0
        self.instruction = info.get("instruction", "")
        # Nemotron VL plans once, on the first frame with objects (in the look thread when threaded).
        # off without NVIDIA_API_KEY (the finals); "fallback" mode only when the parser is unsure.
        m = "off" if info.get("task") == "sort_fixed" else nemotron.mode()
        self._nemotron_pending = m == "primary" or (m == "fallback" and self.parse.confidence != "explicit")
        self.nemotron_plan = None
        self.log(f"[sorter] instruction={info.get('instruction', '')!r} -> {self.full_mapping} "
                 f"({self.parse.confidence}; {'; '.join(self.parse.notes) or 'no notes'})")

    def _nemotron_plan(self, rgb, dets):
        """Ask Nemotron 3.5 Super VL for a validated plan from this frame; on success it replaces the parser
        mapping for the rest of the episode, on any failure the parser mapping stays."""
        self._nemotron_pending = False
        budget = float(os.environ.get("SORTER_NEMOTRON_BUDGET_S", 25))
        plan = nemotron.plan_sort(self.instruction, rgb, dets, parser_mapping=self.parse.mapping,
                                  timeout=min(budget, float(os.environ.get("NEMOTRON_TIMEOUT_S", 60))),
                                  retries=1, budget_s=budget)
        self.nemotron_plan = plan
        if plan.ok:
            self.full_mapping = dict(plan.mapping)
        self.log(f"[sorter] {plan.summary()}")

    def bin_for(self, det):
        return resolve_bin(self.full_mapping, det.color, getattr(det, "shape", None))

    # ------------------------------------------------------------------ look + plan
    def _max_attempts(self, obs):
        """Attempts per object: the config's 2, raised to EXTRA_ATTEMPTS_MAX while EXTRA_ATTEMPTS_RESERVE_S of the
        episode remain. The 2026-11-15 sim runs left objects on the counter after 2 slipped grasps with up to 88 s to
        spare (3-object scenes ended at 32-65 s), and no attempt ever knocked an object off (0 of 91)."""
        base = int(self.cfg["policy"]["max_attempts"])
        t = float(obs.get("t", 0.0)) if isinstance(obs, dict) else 0.0
        if self.time_limit - t >= EXTRA_ATTEMPTS_RESERVE_S:
            return max(base, EXTRA_ATTEMPTS_MAX)
        return base

    def _box_row_x(self):
        """Pelvis x of the box row's near edge."""
        b = self.scene.cfg["bins"]
        return min(float(self.scene.mat_to_pelvis([c[0], c[1], 0.0])[0]) for c in b["centers"].values()) \
            - float(b["outer_size"][1]) / 2

    def _order_key(self, det, bin_name):
        """Pick order: objects within NEAR_BOX_M of the box row last (their grasps tend to fail the bin-rim
        clearance check, and a failing plan costs 5-25 s of IK search: real Drop 3 frames, 2026-11-15), then nearest
        bin first (upstream order)."""
        near = float(det.top[0]) > self._box_row_x() - NEAR_BOX_M
        return (near, float(np.linalg.norm(det.top[:2] - self.planner.bin_xy(bin_name))))

    def _look(self, obs):
        rgb = obs.get("head_rgb")
        # a black frame is "no image yet", not "empty table": the sim's default instance streamed near-black head
        # frames (mean ~1) on 2026-11-15 and the policy ended every episode after 3.7 s with nothing sorted
        if rgb is None or not np.any(rgb) or float(np.asarray(rgb).mean()) < MIN_FRAME_MEAN:
            return ("blank", None, 0)
        dets = self.perception.detect(rgb, obs.get("head_depth"))
        self.last_detections = dets
        if self._nemotron_pending and dets:
            self._nemotron_plan(rgb, dets)
        pcfg = self.cfg["policy"]
        cands = []
        for d in dets:
            xy = d.top[:2]
            if any(np.linalg.norm(xy - f) < pcfg["same_object_radius"] for f in self.failed):
                continue
            n = sum(c for p, c in self.attempts if np.linalg.norm(xy - p) < pcfg["same_object_radius"])
            if n >= self._max_attempts(obs):
                continue
            b = self.bin_for(d)
            if b is None:
                self.log(f"[sorter] no bin for {d} under {self.full_mapping}: skip")
                continue
            cands.append((d, b))
        cands.sort(key=lambda db: self._order_key(db[0], db[1]))
        if hasattr(self.planner, "drop_offsets"):
            self.planner.drop_offsets = {b: DROP_OFFSETS[self.drops.get(b, 0) % len(DROP_OFFSETS)]
                                         for b in self.scene.bin_names}
        for d, b in cands:
            others = [o.top[:2] for o in dets if o is not d]
            p = self.planner.plan(d, self.arm_cmd, self.hand_cmd, bin_name=b, obstacles=others)
            self.plans.append(p)
            if p.ok:
                return ("plan", p, len(dets))
            self.failed.append(d.top[:2])
            self.log(f"[sorter] skip {d}: {p.reason}")
        return ("none", None, len(dets))

    def _attempts_col(self):
        """(xy, count, colour) per attempt; upstream keeps (xy, count) in self.attempts, the colour is kept here."""
        cols = getattr(self, "_attempt_colors", [])
        return [(p, c, cols[i] if i < len(cols) else None) for i, (p, c) in enumerate(self.attempts)]

    def _start(self, plan, t):
        self._attempt_colors = getattr(self, "_attempt_colors", []) + [plan.color]
        tb = plan.target_bin
        if tb in self.scene.bin_names:        # not a relocation to the counter
            self.drops[tb] = self.drops.get(tb, 0) + 1
        return super()._start(plan, t)

    def _after_look(self, res, t):
        kind = res[0]
        if kind == "blank":
            self._blank_looks += 1
            if self._blank_looks <= MAX_BLANK_LOOKS:
                self.state = "look"
                return self._hold()
            self._note(t, "head camera still blank: stopping")
            self.state = "done"
            return self._hold(done=True)
        if kind == "none":
            self._empty_looks += 1
            if self._empty_looks < EMPTY_LOOKS_TO_FINISH and t + 2.0 < self.time_limit:
                self._note(t, f"nothing to sort ({res[2]} detections): looking once more")
                n = int(round(self.cfg["motion"]["settle_s"] * HZ))
                self._enqueue(np.repeat(self.arm_cmd[None], max(n, 1), 0),
                              np.repeat(self.hand_cmd[None], max(n, 1), 0))
                self.state = "executing"       # drains the settle hold, then settle -> look again
                return self._pop()
        else:
            self._empty_looks = 0
        return super()._after_look(res, t)
