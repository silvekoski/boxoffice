"""Head-camera self-calibration recovers a jittered extrinsic from the counter plane and the box rims (mock render)."""
import copy

import numpy as np

from sorter import selfcal
from sorter.synth import SynthRenderer


def _jitter(T, rng, shift=0.015, deg=1.5):
    R = selfcal._rot(rng.uniform(-1, 1, 3) * np.radians(deg) / np.sqrt(3))
    J = np.eye(4)
    J[:3, :3] = R
    J[:3, 3] = rng.uniform(-shift, shift, 3)
    return J @ T


def _cloud(cal, cam, depth, step=3):
    v, u = np.mgrid[0:depth.shape[0]:step, 0:depth.shape[1]:step]
    d = depth[v, u].astype(float)
    ok = (d > 150) & (d < 2000)
    return cal.pixel_to_pelvis(cam, u[ok], v[ok], d[ok])


def test_selfcal_reduces_object_position_error():
    rng = np.random.default_rng(3)
    r = SynthRenderer()
    sc, cal, cam = r.scene, r.cal, r.cam
    T_true = cal.cams[cam].T_pelvis_optical.copy()
    probe = np.array([[0.30, 0.10, sc.counter_z + 0.045], [0.28, -0.12, sc.counter_z + 0.045],
                      [0.32, 0.0, sc.counter_z + 0.045]])
    before, after = [], []
    for _ in range(8):
        rgb, depth = r.render([], rng, depth_noise_mm=1.0)
        uvz = cal.project(cam, probe)                       # true pixels + depth of three probe points
        cal_j = copy.deepcopy(cal)
        cal_j.cams[cam].T_pelvis_optical = _jitter(T_true, rng)
        P = _cloud(cal_j, cam, depth)
        est = selfcal.estimate(P, sc, rng)
        assert est.plane_ok and est.bins_ok, est
        dmm = uvz[:, 2] / cal.cams[cam].depth_scale
        p_j = cal_j.pixel_to_pelvis(cam, uvz[:, 0], uvz[:, 1], dmm)
        p_c = p_j @ est.C[:3, :3].T + est.C[:3, 3]
        before.append(np.linalg.norm(p_j[:, :2] - probe[:, :2], axis=1).max())
        after.append(np.linalg.norm(p_c[:, :2] - probe[:, :2], axis=1).max())
    assert np.median(after) < 0.004, (before, after)
    assert np.median(after) < 0.4 * np.median(before), (before, after)


def _perceive_offsets(mode, deg, shift, seed, monkeypatch):
    """Render a scene with one cube, perceive it with a jittered calibration in `mode`; xy error (m) of the cube."""
    monkeypatch.setenv("SORTER_SELFCAL", mode)
    from sorter.policy import SortingPolicy
    rng = np.random.default_rng(seed)
    r = SynthRenderer()
    pol = SortingPolicy(log=None)
    per = pol.perception
    T_true = per.T0.copy()
    true = np.array([0.30, 0.05, pol.scene.counter_z + 0.0225])
    rgb, depth = r.render([{"color": "red", "shape": "cube", "pos": true, "yaw": 0.2, "size": 0.045, "height": 0.045}],
                          rng, depth_noise_mm=1.0)
    R = selfcal._rot(np.array([0.0, 1.0, 0.0]) * np.radians(deg))      # pitch error
    J = np.eye(4); J[:3, :3] = R; J[:3, 3] = [shift, 0.0, shift]
    per.T0 = J @ T_true
    per.cal.cams[per.cam].T_pelvis_optical = per.T0.copy()
    per.last_selfcal = None
    dets = [d for d in per.detect(rgb, depth) if d.color == "red"]
    per.cal.cams[per.cam].T_pelvis_optical = T_true
    if not dets:                                   # lost entirely (e.g. rejected as off the mat): worst case
        return float("inf"), per.last_selfcal
    return float(np.linalg.norm(dets[0].top[:2] - true[:2])), per.last_selfcal


def test_gross_mode_ignores_sim_sized_jitter(monkeypatch):
    err, est = _perceive_offsets("gross", 0.8, 0.008, 1, monkeypatch)
    assert est is None                                  # no correction: behaves exactly like the nominal calibration


def test_gross_mode_corrects_a_large_tilt(monkeypatch):
    err_off, _ = _perceive_offsets("off", 10.0, 0.0, 2, monkeypatch)
    err_on, est = _perceive_offsets("gross", 10.0, 0.0, 2, monkeypatch)
    assert est is not None and est.plane_ok
    assert err_on < 0.01 and err_on < 0.5 * err_off, (err_on, err_off)
