"""Shape-aware grasp direction: geometry and that aligned triangle plans pass the upstream safety pre-check."""
import numpy as np

from aaltonomous.baselines.classical.config import load_config
from sorter.perception import ShapeDetection
from sorter.planner import aligned_direction
from sorter.policy import SortingPolicy


def test_aligned_direction_is_within_60_deg_of_forward_and_on_a_face_normal():
    for yaw in np.linspace(-np.pi, np.pi, 37):
        d = aligned_direction("triangle", yaw, "face")
        assert d[0] >= np.cos(np.radians(60)) - 1e-9
        # a face normal points away from a vertex: angle to every vertex direction is a multiple of 60 deg, never 0
        verts = yaw + 2 * np.pi * np.arange(3) / 3
        ang = np.degrees(np.arccos(np.clip(np.cos(verts) * d[0] + np.sin(verts) * d[1], -1, 1)))
        assert np.min(np.abs(ang)) > 59
    assert aligned_direction("cylinder", 0.3) is None
    assert aligned_direction("triangle", None) is None


def test_triangle_plan_uses_aligned_hint_and_is_safe():
    pol = SortingPolicy(log=None, config=load_config())
    pol.reset({"instruction": "", "task": "sort_fixed"})
    arm, hand = pol.home.copy(), pol.post["open"].copy()
    z = pol.scene.counter_z + pol.scene.object_height()
    n_ok = 0
    for x, y, yaw in [(0.30, 0.10, 0.2), (0.28, -0.12, -0.5), (0.31, 0.02, 1.0)]:
        det = ShapeDetection("red", np.array([x, y, z]), 500, 400, "depth", shape="triangle", shape_yaw=yaw)
        p = pol.planner.plan(det, arm, hand, bin_name="left")
        if p.ok:
            n_ok += 1
            assert p.safety_clips == 0
    assert n_ok >= 2


def test_oracle_yaw_conversion():
    from sorter.planner import oracle_yaw
    # prism: our yaw = centroid -> vertex; oracle apex direction = oracle yaw + 90 deg
    assert np.isclose(oracle_yaw("triangle", 0.3) + np.pi / 2, 0.3)
    assert oracle_yaw("cube", 0.2) == 0.2
    assert oracle_yaw("cylinder", 0.2) is None and oracle_yaw("triangle", None) is None


def test_face_planner_aligns_cubes_and_prisms_and_is_safe(monkeypatch):
    monkeypatch.setenv("SORTER_PLANNER", "face")
    from sorter.planner import FacePlanner
    pol = SortingPolicy(log=None)
    assert isinstance(pol.planner, FacePlanner)
    pol.reset({"instruction": "", "task": "sort_fixed"})
    arm, hand = pol.home.copy(), pol.post["open"].copy()
    n_ok = n_face = 0
    for shape in ("cube", "triangle", "cylinder"):
        z = pol.scene.counter_z + pol.scene.object_height(shape)
        for x, y, yaw in [(0.30, 0.10, 0.2), (0.28, -0.12, -0.5), (0.31, 0.02, 1.0)]:
            det = ShapeDetection("red", np.array([x, y, z]), 500, 400, "depth", shape=shape,
                                 shape_yaw=None if shape == "cylinder" else yaw)
            p = pol.planner.plan(det, arm, hand, bin_name="left")
            if p.ok:
                n_ok += 1
                n_face += "face-aligned" in (p.reason or "")
                assert p.safety_clips == 0
    assert n_ok >= 8
    assert n_face >= 4          # cubes and prisms mostly get the face-aligned grasp


def test_drop_offsets_cycle_per_bin(monkeypatch):
    monkeypatch.setenv("SORTER_PLANNER", "face")
    from sorter.planner import DROP_OFFSETS
    pol = SortingPolicy(log=None)
    pol.reset({"instruction": "", "task": "sort_fixed"})
    pol.drops = {"left": 1}
    pol.last_detections = []
    pol.perception.detect = lambda rgb, depth=None: []
    pol._look({"head_rgb": np.full((4, 4, 3), 200, np.uint8), "head_depth": np.zeros((4, 4), np.uint16)})
    assert pol.planner.drop_offsets["left"] == DROP_OFFSETS[1]
    assert pol.planner.drop_offsets["center"] == DROP_OFFSETS[0]
