"""fit_cylinder_center recovers a cylinder's centre from its visible side arc, also when the top face is missing."""
import numpy as np

from sorter.perception import fit_cylinder_center

R, H, Z0 = 0.0225, 0.045, -0.05


def cloud(c, top_frac, rng, cam_dir=(-1.0, 0.0), noise=0.001):
    """Points a forward-looking head camera sees: the side facing the camera (+-70 deg) and a share of the top."""
    a0 = np.arctan2(cam_dir[1], cam_dir[0])
    a = a0 + rng.uniform(-np.radians(70), np.radians(70), 600)
    z = rng.uniform(Z0, Z0 + H - 0.004, 600)
    side = np.c_[c[0] + R * np.cos(a), c[1] + R * np.sin(a), z]
    n_top = int(400 * top_frac)
    rr, th = R * np.sqrt(rng.uniform(0, 1, n_top)), rng.uniform(0, 2 * np.pi, n_top)
    top = np.c_[c[0] + rr * np.cos(th), c[1] + rr * np.sin(th), np.full(n_top, Z0 + H)]
    if 0 < top_frac < 1:                      # only the near part of the top face survives the mask
        top = top[top[:, 0] < c[0] - R + 2 * R * top_frac]
    P = np.r_[side, top] + rng.normal(0, noise, (len(side) + len(top), 3))
    return P


def test_fit_recovers_centre_with_full_partial_and_missing_top():
    rng = np.random.default_rng(0)
    for top_frac in (1.0, 0.4, 0.0):
        for _ in range(10):
            c = np.array([rng.uniform(0.25, 0.4), rng.uniform(-0.15, 0.15)])
            P = cloud(c, top_frac, rng)
            z_top = Z0 + H
            near = P[P[:, 2] >= z_top - 0.006][:, :2]
            c0 = near.mean(0) if len(near) else P[:, :2].mean(0)
            got = fit_cylinder_center(P, z_top, R, 0.006, c0)
            assert got is not None
            assert np.linalg.norm(got - c) < 0.004, (top_frac, got - c)
