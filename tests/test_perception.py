"""Shape-aware perception on synthetic head RGB-D frames (true triangular prisms, depth noise and holes)."""
import numpy as np
import pytest

from aaltonomous.baselines.classical.config import load_config
from aaltonomous.interface.calibration import Calibration
from aaltonomous.scene.scene import Scene, shape_polygon
from sorter.perception import ShapePerception, classify_top_face
from sorter.synth import SynthRenderer, random_objects

SC, CAL, CFG = Scene.load(), Calibration.load(), load_config()


@pytest.fixture(scope="module")
def rig():
    return SynthRenderer(SC, CAL), ShapePerception(CFG, SC, CAL)


def match(dets, objs):
    out = []
    for o in objs:
        cands = [d for d in dets if d.color == o["color"]]
        assert cands, f"missed {o['color']} {o['shape']}"
        out.append((o, min(cands, key=lambda d: np.linalg.norm(d.top[:2] - o["pos"][:2]))))
    return out


@pytest.mark.parametrize("shape", ["cube", "cylinder", "triangle"])
def test_classify_ideal_outlines(shape):
    rng = np.random.default_rng(0)
    for rot in np.linspace(-0.8, 0.8, 5):
        poly = shape_polygon(shape, SC.object_dims(shape)["apothem"], rot)
        # sample the filled polygon on a jittered 1 mm grid, like deprojected depth pixels
        g = np.stack(np.meshgrid(np.arange(-0.03, 0.03, 0.001), np.arange(-0.03, 0.03, 0.001)), -1).reshape(-1, 2)
        g = g + rng.normal(0, 0.0003, g.shape)
        e = np.roll(poly, -1, axis=0) - poly                      # CCW convex polygon: all cross products >= 0
        rel = g[:, None, :] - poly[None]
        inside = np.all(e[None, :, 0] * rel[..., 1] - e[None, :, 1] * rel[..., 0] >= 0, axis=1)
        got, scores, _ = classify_top_face(g[inside])
        assert got == shape, (shape, rot, scores)


def test_detects_every_object_with_shape(rig):
    r, p = rig
    rng = np.random.default_rng(0)
    n = correct = 0
    for _ in range(12):
        objs = random_objects(rng, SC)
        rgb, depth = r.render(objs, rng, depth_noise_mm=1.5, hole_frac=0.1)
        for o, d in match(p.detect(rgb, depth), objs):
            top = o["pos"] + [0, 0, o["height"] / 2]
            assert np.linalg.norm(d.top - top) < 0.012, (o, d)
            n += 1
            correct += d.shape == o["shape"]
    assert correct / n >= 0.95, f"shape accuracy {correct}/{n}"


@pytest.mark.parametrize("gain,tint", [(0.3, (1, 1, 1)), (0.4, (1.15, 1.0, 0.75)), (1.4, (0.8, 0.95, 1.2))])
def test_lighting_changes(rig, gain, tint):
    """Held-out variants change lighting: dim, warm and cool frames still give every object, nothing extra."""
    r, p = rig
    rng = np.random.default_rng(5)
    for _ in range(4):
        objs = random_objects(rng, SC)
        rgb, depth = r.render(objs, rng, depth_noise_mm=1.5, hole_frac=0.1)
        img = np.clip(rgb * gain * np.asarray(tint), 0, 255).astype(np.uint8)
        dets = p.detect(img, depth)
        match(dets, objs)
        assert len(dets) == len(objs)


def test_blank_frame_gives_nothing(rig):
    _, p = rig
    assert p.detect(np.zeros((480, 640, 3), np.uint8), np.zeros((480, 640), np.uint16)) == []


def test_no_depth_gives_detections_without_shape(rig):
    r, p = rig
    rng = np.random.default_rng(3)
    objs = random_objects(rng, SC, n=3)
    rgb, _ = r.render(objs)
    dets = p.detect(rgb, np.zeros(rgb.shape[:2], np.uint16))
    assert sorted(d.color for d in dets) == sorted(o["color"] for o in objs)
    assert all(d.method == "plane" for d in dets)
