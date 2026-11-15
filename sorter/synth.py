"""Synthetic head RGB-D frames for offline tests: the organisers' mock Renderer plus true triangular prisms.

The upstream Renderer (baselines/classical/mock_world.py) draws triangles as boxes ("a blob is a blob" for the
baseline). Shape-aware perception needs the real outline, so this subclass ray-casts every object as a convex
polytope (cube, triangle) or uses the upstream cylinder. Frames go through the same calibration.yaml camera.

    r = SynthRenderer()
    rgb, depth = r.render([{"color": "red", "shape": "triangle", "pos": p_pelvis_centre, "yaw": 0.3,
                            "size": 0.045, "height": 0.045}], rng, depth_noise_mm=1.5, hole_frac=0.1)
"""
from __future__ import annotations

import numpy as np

from aaltonomous.baselines.classical.mock_world import Renderer
from aaltonomous.interface.calibration import Calibration
from aaltonomous.scene.scene import Scene


def prism_planes(shape, size, height, yaw):
    """Outward half-spaces (n (k,3), d (k,)) with n.p <= d, object frame centred on the centroid."""
    if shape == "triangle":
        apothem, angles = size / 3.0, np.pi / 2 + np.pi + 2 * np.pi * np.arange(3) / 3   # opposite each vertex
    else:  # cube
        apothem, angles = size / 2.0, 2 * np.pi * np.arange(4) / 4
    angles = angles + yaw
    n = [[np.cos(a), np.sin(a), 0.0] for a in angles] + [[0, 0, 1.0], [0, 0, -1.0]]
    d = [apothem] * len(angles) + [height / 2, height / 2]
    return np.asarray(n, float), np.asarray(d, float)


class SynthRenderer(Renderer):
    def __init__(self, scene: Scene | None = None, cal: Calibration | None = None, cam="head"):
        super().__init__(scene or Scene.load(), cal or Calibration.load(), cam)

    def _polytope(self, rgb, zb, center, normals, ds, col, bound):
        win = self._pixels(center, np.eye(3), np.array([bound, bound, ds[-1]]))
        if win is None:
            return
        d = self.rays[win]                                   # (h, w, 3)
        o = self.o - center
        den = d @ normals.T                                  # (h, w, k)
        num = ds - normals @ o                               # (k,)
        with np.errstate(divide="ignore", invalid="ignore"):
            t = num / den
        enter = np.where(den < 0, t, -np.inf)
        leave = np.where(den > 0, t, np.inf)
        parallel_out = (den == 0) & (num < 0)
        tmin, tmax = enter.max(-1), leave.min(-1)
        hit = (tmin <= tmax) & (tmin > 0) & ~parallel_out.any(-1)
        nz = np.abs(normals[enter.argmax(-1), 2])
        self._write(rgb, zb, win, hit, tmin, nz, col)

    def render(self, objects, rng=None, depth_noise_mm=0.0, hole_frac=0.0):
        rgb, zb = self._bg[0].copy(), self._bg[1].copy()
        for ob in objects:
            col = self.colors[ob["color"]]
            s, h = ob["size"], ob.get("height", ob["size"])
            shape = ob.get("shape", "cube")
            if shape in ("cylinder", "circle"):
                self._cylinder(rgb, zb, ob["pos"], s / 2, h / 2, col)
            else:
                n, d = prism_planes(shape, s, h, ob.get("yaw", 0.0))
                self._polytope(rgb, zb, np.asarray(ob["pos"], float), n, d, col, bound=s)
        depth = np.where(np.isfinite(zb), zb * 1000.0, 0.0)
        if rng is not None and depth_noise_mm > 0:
            depth = depth + rng.normal(0, depth_noise_mm, depth.shape)
        if rng is not None and hole_frac > 0:
            depth[rng.random(depth.shape) < hole_frac] = 0
        return np.clip(rgb, 0, 255).astype(np.uint8), np.clip(depth, 0, 65535).astype(np.uint16)


def random_objects(rng, scene: Scene | None = None, n=None, shapes=("cube", "cylinder", "triangle")):
    """A layout like tasks.sample_layout (object band, >= 8 cm apart, yaw +-45 deg) as renderer objects."""
    from aaltonomous.interface.tasks import sample_layout
    sc = scene or Scene.load()
    kw = sc.layout_kwargs() if hasattr(sc, "layout_kwargs") else {}
    if n is not None:
        kw.update(n_min=n, n_max=n)
    layout = sample_layout(rng, shapes=shapes, **kw)
    out = []
    for c in layout:
        h = sc.object_height(c["shape"])
        out.append({"color": c["color"], "shape": c["shape"], "yaw": c["yaw"], "size": sc.size, "height": h,
                    "pos": sc.mat_to_pelvis(sc.cube_spawn_mat(c))})
    return out
