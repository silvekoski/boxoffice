"""Nemotron sort planner with the HTTP call mocked: validation, grounding self-check, re-ask, fallback, policy hook."""
import json
import urllib.error

import numpy as np
import pytest

from aaltonomous.baselines.classical.mock_world import make_mock_env
from sorter import nemotron
from sorter.instruction import parse_instruction
from sorter.nemotron import NemotronError, compare, plan_sort, validate
from sorter.policy import SortingPolicy


class Det:
    def __init__(self, color, shape, top=(0.3, 0.0, 0.8), uv=(100, 100)):
        self.color, self.shape, self.top, self.uv = color, shape, np.array(top), uv


DETS = [Det("red", "cube"), Det("blue", "cylinder"), Det("yellow", "triangle")]


def call(args, as_text=False):
    if as_text:
        return {"choices": [{"message": {"role": "assistant", "content": "Plan: " + json.dumps(args)}}]}
    return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
        {"id": "c1", "type": "function", "function": {"name": "submit_sort_plan", "arguments": json.dumps(args)}}]}}]}


GOOD = {"reasoning": "cubes left, rest right",
        "rules": [{"color": "any", "shape": "cube", "bin": "left"}, {"color": "any", "shape": "any", "bin": "right"}],
        "objects": [{"id": 0, "bin": "left"}, {"id": 1, "bin": "right"}, {"id": 2, "bin": "right"}]}


class FakePost:
    def __init__(self, *responses):
        self.responses, self.payloads = list(responses), []

    def __call__(self, payload, timeout, retries=0):
        self.payloads.append(json.loads(json.dumps(payload)))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    monkeypatch.delenv("SORTER_NEMOTRON", raising=False)
    nemotron._CACHE.clear()


def test_valid_plan_maps_to_scorer_keys():
    post = FakePost(call(GOOD))
    p = plan_sort("Cubes go left, everything else right.", np.zeros((48, 64, 3), np.uint8), DETS, post=post)
    assert p.ok and p.attempts == 1
    assert p.mapping == {"cube": "left", "default": "right"}
    body = post.payloads[0]
    assert body["model"] == nemotron.DEFAULT_MODEL
    assert body["tool_choice"]["function"]["name"] == "submit_sort_plan"
    parts = body["messages"][1]["content"]
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert "id 2: yellow triangle" in parts[0]["text"]


def test_grounding_mismatch_is_re_asked_and_fixed():
    bad = dict(GOOD, objects=[{"id": 0, "bin": "left"}, {"id": 1, "bin": "left"}, {"id": 2, "bin": "right"}])
    post = FakePost(call(bad), call(GOOD))
    p = plan_sort("Cubes go left, everything else right.", None, DETS, post=post)
    assert p.ok and p.attempts == 2
    assert "your rules give right" in p.errors[0][0]
    follow_up = post.payloads[1]["messages"]
    assert follow_up[-1]["role"] == "tool" and "rejected" in follow_up[-1]["content"]


def test_invalid_twice_falls_back():
    bad = {"reasoning": "", "rules": [{"color": "green", "shape": "any", "bin": "left"}], "objects": []}
    p = plan_sort("x", None, DETS, post=FakePost(call(bad), call(bad)))
    assert not p.ok and p.attempts == 2 and "unknown colour" in p.error


def test_validation_rules():
    m, _, errs = validate({"rules": [{"color": "red", "shape": "any", "bin": "left"},
                                     {"color": "red", "shape": "any", "bin": "right"},
                                     {"color": "red", "shape": "cube", "bin": "middle"}],
                           "objects": [{"id": 7, "bin": "left"}, {"id": 0, "bin": "left"}, {"id": 0, "bin": "left"}]},
                          DETS)
    joined = " | ".join(errs)
    assert m == {"red": "left"}
    for s in ("conflict", "unknown bin", "id 7 does not exist", "listed twice", "missing from the list: ids [1, 2]"):
        assert s in joined, joined


def test_text_json_fallback_and_skip():
    args = {"reasoning": "only red named", "rules": [{"color": "red", "shape": "any", "bin": "center"}],
            "objects": [{"id": 0, "bin": "center"}, {"id": 1, "bin": "skip"}, {"id": 2, "bin": "skip"}]}
    p = plan_sort("Red to the middle.", None, DETS, post=FakePost(call(args, as_text=True)))
    assert p.ok and p.mapping == {"red": "center"}


def test_http_errors_degrade_and_400_tool_choice_retries_without_it():
    p = plan_sort("x", None, DETS, post=FakePost(NemotronError("network: timed out")))
    assert not p.ok and "timed out" in p.error and "unavailable" in p.summary()
    post = FakePost(NemotronError("HTTP 400: tool_choice not supported"), call(GOOD))
    p = plan_sort("Cubes left, rest right", None, DETS, post=post)
    assert p.ok and "tool_choice" not in post.payloads[1]


def test_not_configured(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY")
    p = plan_sort("x", None, DETS, post=FakePost())
    assert not p.ok and "not configured" in p.error
    assert nemotron.mode() == "off"


def test_cache_and_compare():
    post = FakePost(call(GOOD))
    parser = parse_instruction("Cubes go left, everything else right.").mapping
    a = plan_sort("Cubes go left, everything else right.", None, DETS, parser_mapping=parser, post=post)
    b = plan_sort("Cubes go left, everything else right.", None, DETS, parser_mapping={"red": "left"}, post=post)
    assert a.disagreements == [] and b.cached and len(post.payloads) == 1
    assert ("blue", "cube", None, "left") in compare(b.mapping, {"red": "left"})


def test_post_retries_429_then_succeeds(monkeypatch):
    calls = []

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(call(GOOD)).encode()

    def urlopen(req, timeout):
        calls.append(req.full_url)
        if len(calls) == 1:
            raise urllib.error.HTTPError(req.full_url, 429, "rate", {}, None)
        return Resp()

    monkeypatch.setattr(nemotron.urllib.request, "urlopen", urlopen)
    out = nemotron._post({"model": "m"}, 5, retries=2, sleep=lambda s: None)
    assert out["choices"] and len(calls) == 2 and calls[0].endswith("/chat/completions")


def test_policy_uses_nemotron_plan_once(monkeypatch):
    seen = []

    def fake_plan(instruction, rgb, dets, parser_mapping=None, **kw):
        seen.append((instruction, rgb.shape, len(dets)))
        return nemotron.NemotronPlan(True, {"default": "left"}, reasoning="all left", attempts=1)

    monkeypatch.setattr(nemotron, "plan_sort", fake_plan)
    env = make_mock_env(seed=0)
    pol = SortingPolicy(log=None, safety=env.filter.cfg)
    obs = env.reset()
    pol.reset({"instruction": "Everything goes in the left bin.", "task": "sort_language"})
    for _ in range(200):
        obs, info = env.step(pol.act(obs))
        if pol.nemotron_plan is not None or info["episode_over"]:
            break
    assert len(seen) == 1 and pol.full_mapping == {"default": "left"}
    for _ in range(50):
        obs, info = env.step(pol.act(obs))
    assert len(seen) == 1


def test_policy_without_key_keeps_parser(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY")
    monkeypatch.setattr(nemotron, "plan_sort", lambda *a, **k: pytest.fail("must not call Nemotron"))
    pol = SortingPolicy(log=None)
    pol.reset({"instruction": "Red to the right, blue left, yellow center.", "task": "sort_language"})
    assert not pol._nemotron_pending and pol.full_mapping == {"red": "right", "blue": "left", "yellow": "center"}
    monkeypatch.setenv("NVIDIA_API_KEY", "k")
    monkeypatch.setenv("SORTER_NEMOTRON", "fallback")
    pol.reset({"instruction": "Red to the right, blue left, yellow center.", "task": "sort_language"})
    assert not pol._nemotron_pending
    pol.reset({"instruction": "Do your best!", "task": "sort_language"})
    assert pol._nemotron_pending
