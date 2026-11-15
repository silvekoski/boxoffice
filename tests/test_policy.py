"""SortingPolicy end to end on the organisers' rendered mock world, and the policy server through the real runner."""
import tempfile
import threading

import numpy as np
import pytest

from aaltonomous.baselines.classical.mock_world import make_mock_env
from aaltonomous.deploy.policy_server import serve
from aaltonomous.deploy.replay import load_obs, replay
from aaltonomous.deploy.runner import run
from aaltonomous.scene.scene import resolve_bin
from sorter.policy import SortingPolicy
from sorter.server import SorterServerPolicy
from sorter.synth import SynthRenderer


def episode(seed, instruction, task="sort_language"):
    env = make_mock_env(seed=seed)
    env.backend.renderer = SynthRenderer(env.scene)          # true triangles instead of boxes
    pol = SortingPolicy(log=None, safety=env.filter.cfg)
    obs = env.reset()
    pol.reset({"instruction": instruction, "task": task})
    obs["instruction"] = instruction
    while True:
        obs, info = env.step(pol.act(obs))
        if info["episode_over"]:
            break
    out = [env.scene.classify_cube(o["pos"], 0.0, o["color"], {o["color"]: resolve_bin(pol.full_mapping, o["color"], o["shape"])})
           for o in env.backend.objects]
    return pol, info, out


@pytest.mark.parametrize("seed,instruction", [
    (0, "Sort the objects: red into right, blue into left, yellow into center."),
    (1, "Blue belongs on the left. Yellow belongs on the right. Red belongs in the center."),
])
def test_language_episode_sorts_by_instruction(seed, instruction):
    pol, info, out = episode(seed, instruction)
    assert info["end_reason"] in ("done", "time_limit")
    assert info["safety_summary"]["clipped_steps"] == 0, info["safety_summary"]
    assert "wrong" not in out and "off" not in out, out
    assert out.count("correct") >= 2, (out, pol.events)


def test_blank_camera_does_not_end_episode():
    env = make_mock_env(seed=2)
    pol = SortingPolicy(log=None, safety=env.filter.cfg)
    obs = env.reset()
    pol.reset({"instruction": obs["instruction"], "task": "sort_fixed"})
    for _ in range(40):                                      # 40 blank frames first
        blank = dict(obs, head_rgb=np.zeros_like(obs["head_rgb"]), head_depth=np.zeros_like(obs["head_depth"]))
        a = pol.act(blank)
        assert not a["done"]
        obs, info = env.step(a)
    while pol.state != "executing":
        obs, info = env.step(pol.act(obs))
        assert not info["episode_over"]
    assert pol.plans and pol.plans[-1].ok


def _serve(port):
    ready = threading.Event()
    threading.Thread(target=serve, args=(SorterServerPolicy(), port, "127.0.0.1", ready), daemon=True).start()
    assert ready.wait(30)
    return ready


def test_server_replay_rate_and_shapes():
    ready = _serve(8211)
    try:
        res = replay("ws://127.0.0.1:8211", load_obs(None, 150, synthetic=True))
    finally:
        ready.server.shutdown()
    assert res["pass"], res
    assert res["command_hz"] >= 27


def test_server_through_runner_mock_backend():
    ready = _serve(8212)
    try:
        with tempfile.TemporaryDirectory() as d:
            s, _ = run("mock", "ws://127.0.0.1:8212", "t", 1, out=d, time_limit=6.0)
    finally:
        ready.server.shutdown()
    assert s[0]["safety"]["clipped_steps"] == 0, s[0]
    assert s[0]["end_reason"] in ("done", "time_limit"), s[0]


def test_attempts_are_the_configs():
    pol = SortingPolicy(log=None)
    pol.reset({"instruction": "", "task": "sort_fixed"})
    assert pol._max_attempts({"t": 10.0}) == int(pol.cfg["policy"]["max_attempts"]) == 2


def test_black_frame_is_blank_not_empty():
    pol = SortingPolicy(log=None)
    pol.reset({"instruction": "", "task": "sort_fixed"})
    dark = np.ones((480, 640, 3), np.uint8)          # mean 1: a camera that streams black
    assert pol._look({"head_rgb": dark, "head_depth": np.zeros((480, 640), np.uint16), "t": 1.0})[0] == "blank"
