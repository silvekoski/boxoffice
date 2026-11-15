"""Perception on real venue head frames (Hugging Face zupermiez/g1_junction_drop_3, Apache-2.0, first frame + 0.2 s
of episodes 2 and 6). The real camera shows red objects at H 11-13 (upstream red stops at 8), the orange-paper boxes at
H ~4 (inside upstream red) and the dark robot hands at H ~101 V < 75 (inside upstream blue). Before the fixes in
sorter/perception.py these frames gave box flaps as red objects, hands as blue objects and missed the red cylinders."""
from pathlib import Path

import cv2
import numpy as np
import pytest

from sorter.policy import SortingPolicy

FIX = Path(__file__).parent / "fixtures"


def load(i):
    rgb = cv2.cvtColor(cv2.imread(str(FIX / f"drop3_ep{i:02d}_rgb.png")), cv2.COLOR_BGR2RGB)
    depth = np.load(FIX / f"drop3_ep{i:02d}_depth.npz")["depth"]
    return rgb, depth


@pytest.fixture(scope="module")
def per():
    return SortingPolicy(log=None).perception


# ground truth counted by eye on the frames (objects fully on the table in front of the boxes)
TRUTH = {2: {"red": 2, "yellow": 0, "blue": 1}, 6: {"red": 1, "yellow": 2, "blue": 2}}   # ep02 prism touches the box row: may be skipped


@pytest.mark.parametrize("ep", sorted(TRUTH))
def test_real_frame_colours_and_no_boxes_or_hands(per, ep):
    rgb, depth = load(ep)
    dets, rej = per.detect(rgb, depth, debug=True)
    by = {c: sum(d.color == c for d in dets) for c in ("red", "yellow", "blue")}
    for c, n in TRUTH[ep].items():
        assert by[c] >= n, (c, by, dets)                     # every real object found
        assert by[c] <= n + 1, (c, by, dets)                 # at most one spurious blob per colour
    sc = per.scene
    near = min(float(c[1]) for c in sc.cfg["bins"]["centers"].values()) - sc.cfg["bins"]["outer_size"][1] / 2
    for d in dets:                                           # nothing on the box row (the orange flaps)
        assert sc.pelvis_to_mat(d.top)[1] < near + 0.06, d
        assert getattr(d, "v_med", 255) is None or d.v_med >= 100, d    # no dark hand blobs
