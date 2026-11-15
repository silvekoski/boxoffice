"""Nemotron 3.5 Super VL sort planner: head camera frame + our detections + the instruction -> a validated sort plan.

Optional and online. The finals have no network, so the offline parser (sorter.instruction) stays the default and
the fallback. With NVIDIA_API_KEY set, the policy calls this once per episode, on the first non-blank head frame:

    plan = plan_sort(instruction, rgb, detections, parser_mapping=parse.mapping)
    plan.mapping   # {"red": "left", ("red", "cube"): "right", "default": "center", ...}, same keys as the parser
    plan.objects   # [{"id": 0, "bin": "left", "why": "..."}, ...]  one entry per detection
    plan.ok        # False -> keep the parser mapping (plan.error says why)

How the output is kept honest:
  * Structured output: one forced tool call `submit_sort_plan` with enums for colour, shape and bin. Rules use the
    keys of the organisers' scorer (resolve_bin), so the plan drops into the existing planner unchanged.
  * Validation against the known world: colours, shapes and bins must be from the task; detection ids must exist;
    every detection must be covered once; rules may not conflict.
  * Grounding self-check: the bin the model states per object must equal what its own rules give for that object's
    detected colour and shape (resolve_bin). A mismatch means the rules do not say what the model meant.
  * Re-ask: on any validation error the errors go back to the model as the tool result, up to NEMOTRON_ATTEMPTS
    (default 2) attempts. Still invalid -> not ok, the parser mapping stays.
  * Cross-check: the plan is compared with the offline parser per colour x shape; disagreements are logged.

Env: NVIDIA_API_KEY (required), NEMOTRON_BASE_URL, NEMOTRON_MODEL, NEMOTRON_TIMEOUT_S (per request, default 60),
NEMOTRON_ATTEMPTS (default 2). No extra dependencies: urllib + cv2 (PNG encode).

Smoke test once a key exists (one synthetic head frame, one call):
    NVIDIA_API_KEY=... PYTHONPATH=.:upstream .venv/bin/python -m sorter.nemotron --synthetic \
        "Cubes go left, everything else goes right."
    NVIDIA_API_KEY=... PYTHONPATH=.:upstream .venv/bin/python -m sorter.nemotron --eval   # 17 paraphrases vs parser
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from .instruction import BINS, COLORS, SHAPES

LABEL = "Nemotron 3.5 Super VL"
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"
TOOL_NAME = "submit_sort_plan"

TOOL = {"type": "function", "function": {
    "name": TOOL_NAME,
    "description": "Submit the sort plan for the objects on the table. Rules are evaluated like this: for an object "
                   "with colour C and shape S the first matching rule in the order (C,S), (C,any), (any,S), "
                   "(any,any) gives its bin. An object no rule matches is skipped (left on the table).",
    "parameters": {
        "type": "object",
        "properties": {
            "reasoning": {"type": "string", "description": "One or two sentences: how you read the instruction."},
            "rules": {"type": "array", "items": {
                "type": "object",
                "properties": {"color": {"type": "string", "enum": [*COLORS, "any"]},
                               "shape": {"type": "string", "enum": [*SHAPES, "any"]},
                               "bin": {"type": "string", "enum": list(BINS)}},
                "required": ["color", "shape", "bin"]}},
            "objects": {"type": "array", "description": "One entry per detected object id.", "items": {
                "type": "object",
                "properties": {"id": {"type": "integer"},
                               "bin": {"type": "string", "enum": [*BINS, "skip"]},
                               "why": {"type": "string"}},
                "required": ["id", "bin"]}},
        },
        "required": ["reasoning", "rules", "objects"]}}}

SYSTEM = (
    "You plan pick-and-place sorting for a Unitree G1 humanoid robot. In front of it is a table with small "
    "objects (colours: red, yellow, blue; shapes: cube, cylinder, triangle = triangular prism) and three bins: "
    "left, center, right (from the robot's point of view). A person gives a free-text instruction that says which "
    "objects go to which bin. You get the robot's head camera image, the list of objects its detector found, and "
    "the instruction. Call submit_sort_plan exactly once.\n"
    "Rules:\n"
    "- Encode the instruction as rules; use 'any' for a colour or shape the instruction does not name. "
    "'Everything else' / 'the rest' is a rule with color=any, shape=any.\n"
    "- 'As usual' / 'the default' means red->left, yellow->center, blue->right. 'Reverse' / 'opposite' means "
    "red->right, yellow->center, blue->left. 'Swap A and B' exchanges their bins in the default.\n"
    "- If the instruction gives two of the three colours one bin each and the third colour is clearly implied to "
    "take the remaining bin, add that rule. Otherwise do not invent rules: a wrong bin costs a point, a skipped "
    "object costs nothing.\n"
    "- Then list every detected object id with the bin your rules give it (or 'skip'). Use the detector's colour "
    "and shape for each id; use the image to check what is on the table.")


class NemotronError(RuntimeError):
    pass


@dataclass
class NemotronPlan:
    ok: bool
    mapping: dict = field(default_factory=dict)
    objects: list = field(default_factory=list)
    reasoning: str = ""
    attempts: int = 0
    latency_s: float = 0.0
    errors: list = field(default_factory=list)       # validation errors of each rejected attempt
    disagreements: list = field(default_factory=list)  # (colour, shape, parser bin, nemotron bin)
    error: str = ""
    cached: bool = False

    def summary(self):
        if not self.ok:
            return f"{LABEL}: unavailable ({self.error}); parser mapping kept"
        s = (f"{LABEL}: {fmt_mapping(self.mapping)} in {self.latency_s:.1f} s, {self.attempts} attempt(s)"
             f"{' (cached)' if self.cached else ''}; {self.reasoning}")
        if self.errors:
            s += f"; re-asked after: {' | '.join('; '.join(e) for e in self.errors)}"
        if self.disagreements:
            s += "; differs from parser on " + ", ".join(f"{c} {sh}: parser {p} vs {n}"
                                                        for c, sh, p, n in self.disagreements)
        return s


def fmt_mapping(m):
    def k(key):
        return "+".join(key) if isinstance(key, tuple) else str(key)
    return "{" + ", ".join(f"{k(key)}->{b}" for key, b in m.items()) + "}"


def configured() -> bool:
    return bool(os.environ.get("NVIDIA_API_KEY", "").strip())


def mode() -> str:
    """SORTER_NEMOTRON: off | fallback (only when the parser is unsure) | primary (default when a key is set)."""
    m = os.environ.get("SORTER_NEMOTRON", "primary").strip().lower()
    if m in ("0", "off", "no", "false", "") or not configured():
        return "off"
    return "fallback" if m == "fallback" else "primary"


# ------------------------------------------------------------------ resolve (same order as scene.resolve_bin)
def _resolve(mapping, color, shape):
    for k in ((color, shape), color, shape, "default"):
        if k is not None and k in mapping:
            return mapping[k]
    return None


# ------------------------------------------------------------------ validation
def validate(args, detections):
    """Tool-call arguments -> (mapping, objects, errors). errors empty = valid."""
    errors, mapping, objects = [], {}, []
    if not isinstance(args, dict):
        return {}, [], ["arguments are not a JSON object"]
    rules = args.get("rules")
    if not isinstance(rules, list) or not rules:
        errors.append("rules must be a non-empty list")
        rules = []
    for i, r in enumerate(rules):
        if not isinstance(r, dict):
            errors.append(f"rule {i} is not an object")
            continue
        c, s, b = (str(r.get(x, "any")).strip().lower() for x in ("color", "shape", "bin"))
        if c not in (*COLORS, "any"):
            errors.append(f"rule {i}: unknown colour {c!r} (use {', '.join(COLORS)} or any)")
            continue
        if s not in (*SHAPES, "any"):
            errors.append(f"rule {i}: unknown shape {s!r} (use {', '.join(SHAPES)} or any)")
            continue
        if b not in BINS:
            errors.append(f"rule {i}: unknown bin {b!r} (use {', '.join(BINS)})")
            continue
        key = (c, s) if c != "any" and s != "any" else c if c != "any" else s if s != "any" else "default"
        if key in mapping and mapping[key] != b:
            errors.append(f"rules conflict for {key}: {mapping[key]} and {b}")
            continue
        mapping[key] = b
    ids = {i: d for i, d in enumerate(detections)}
    seen = set()
    for o in args.get("objects") or []:
        if not isinstance(o, dict) or not isinstance(o.get("id"), int) or isinstance(o.get("id"), bool):
            errors.append(f"object entry without an integer id: {o!r}")
            continue
        i, b = o["id"], str(o.get("bin", "")).strip().lower()
        if i not in ids:
            errors.append(f"object id {i} does not exist (ids: {sorted(ids)})")
            continue
        if i in seen:
            errors.append(f"object id {i} listed twice")
            continue
        seen.add(i)
        d = ids[i]
        want = _resolve(mapping, d.color, getattr(d, "shape", None)) or "skip"
        if b != want:
            errors.append(f"object {i} ({d.color} {getattr(d, 'shape', None) or 'unknown shape'}): you said {b}, "
                          f"but your rules give {want}; fix the rules or the object")
        objects.append({"id": i, "bin": b, "why": str(o.get("why", ""))[:200]})
    missing = sorted(set(ids) - seen)
    if missing:
        errors.append(f"objects missing from the list: ids {missing}")
    return mapping, objects, errors


def compare(nemo_mapping, parser_mapping):
    """(colour, shape, parser bin, nemotron bin) for every colour x shape where the two differ."""
    out = []
    for c in COLORS:
        for s in SHAPES:
            p, n = _resolve(parser_mapping or {}, c, s), _resolve(nemo_mapping, c, s)
            if p != n:
                out.append((c, s, p, n))
    return out


# ------------------------------------------------------------------ HTTP
def _post(payload, timeout, retries=3, sleep=time.sleep):
    base = os.environ.get("NEMOTRON_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    body = json.dumps(payload).encode()
    last = None
    for k in range(retries + 1):
        req = urllib.request.Request(f"{base}/chat/completions", data=body, method="POST", headers={
            "Authorization": f"Bearer {os.environ.get('NVIDIA_API_KEY', '').strip()}",
            "Content-Type": "application/json", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            last = NemotronError(f"HTTP {e.code}: {detail}")
            if e.code != 429 and e.code < 500:
                raise last from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = NemotronError(f"network: {e}")
        if k < retries:
            sleep(min(8.0, 1.0 * 2 ** k) + random.random() * 0.3)
    raise last


def _tool_args(resp):
    """Arguments of the submit_sort_plan call; falls back to a JSON object in the message text."""
    try:
        msg = resp["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as e:
        raise NemotronError(f"malformed response: {str(resp)[:200]}") from e
    for tc in msg.get("tool_calls") or []:
        f = tc.get("function") or {}
        if f.get("name") in (TOOL_NAME, None):
            a = f.get("arguments")
            try:
                return (json.loads(a) if isinstance(a, str) else a), msg, tc.get("id")
            except json.JSONDecodeError:
                return {"_unparsable": a}, msg, tc.get("id")
    text = msg.get("content") or ""
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            return json.loads(m.group(0)), msg, None
        except json.JSONDecodeError:
            pass
    return {"_unparsable": text[:300]}, msg, None


def encode_png(rgb, max_side=768):
    import cv2
    h, w = rgb.shape[:2]
    s = min(1.0, max_side / max(h, w))
    img = rgb if s >= 1.0 else cv2.resize(rgb, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".png", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    if not ok:
        raise NemotronError("PNG encode failed")
    return base64.b64encode(buf.tobytes()).decode()


def describe(detections):
    lines = []
    for i, d in enumerate(detections):
        x, y, _ = (float(v) for v in d.top)
        u, v = (int(round(float(t))) for t in (getattr(d, "uv", None) or (0, 0)))
        lines.append(f"id {i}: {d.color} {getattr(d, 'shape', None) or 'unknown-shape'}, image pixel ({u},{v}), "
                     f"{x * 100:.0f} cm ahead, {abs(y) * 100:.0f} cm to the robot's {'left' if y >= 0 else 'right'}")
    return "\n".join(lines) or "(the detector found no objects)"


_CACHE: dict = {}


def plan_sort(instruction, rgb=None, detections=(), parser_mapping=None, timeout=None, attempts=None,
              retries=3, budget_s=None, post=_post) -> NemotronPlan:
    """One validated sort plan. Never raises: failures come back as NemotronPlan(ok=False, error=...).
    retries: HTTP retries per attempt (429 / 5xx / network); budget_s: no new attempt after this many seconds."""
    t0 = time.monotonic()
    detections = list(detections)
    if not configured():
        return NemotronPlan(False, error="Nemotron not configured (NVIDIA_API_KEY unset)")
    timeout = float(timeout or os.environ.get("NEMOTRON_TIMEOUT_S", 60))
    attempts = int(attempts or os.environ.get("NEMOTRON_ATTEMPTS", 2))
    model = os.environ.get("NEMOTRON_MODEL", DEFAULT_MODEL)
    user = [{"type": "text", "text": f"Instruction: {instruction!r}\n\nDetected objects:\n{describe(detections)}"}]
    img_b64 = None
    if rgb is not None:
        try:
            img_b64 = encode_png(rgb)
            user.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}})
        except Exception as e:  # noqa: BLE001 - a bad frame must not cost the plan; text-only still works
            user[0]["text"] += f"\n(no image: {e})"
    key = hashlib.sha256(json.dumps([model, instruction, describe(detections), img_b64]).encode()).hexdigest()
    if key in _CACHE:
        p = _CACHE[key]
        return NemotronPlan(True, dict(p.mapping), list(p.objects), p.reasoning, p.attempts, 0.0, list(p.errors),
                            compare(p.mapping, parser_mapping), cached=True)
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    all_errors = []
    for n in range(1, attempts + 1):
        if budget_s is not None and n > 1 and time.monotonic() - t0 > budget_s:
            all_errors.append([f"time budget {budget_s:.0f} s used up"])
            break
        payload = {"model": model, "messages": messages, "tools": [TOOL], "temperature": 0.0, "max_tokens": 2048,
                   "tool_choice": {"type": "function", "function": {"name": TOOL_NAME}}}
        try:
            resp = post(payload, timeout, retries)
        except NemotronError as e:
            if n == 1 and str(e).startswith("HTTP 400") and "tool" in str(e).lower():
                # endpoint refuses forced tool_choice: ask for the same JSON in the message text instead
                payload.pop("tool_choice")
                try:
                    resp = post(payload, timeout, retries)
                except NemotronError as e2:
                    return NemotronPlan(False, attempts=n, latency_s=time.monotonic() - t0, errors=all_errors,
                                        error=str(e2))
            else:
                return NemotronPlan(False, attempts=n, latency_s=time.monotonic() - t0, errors=all_errors,
                                    error=str(e))
        except Exception as e:  # noqa: BLE001
            return NemotronPlan(False, attempts=n, latency_s=time.monotonic() - t0, errors=all_errors, error=str(e))
        try:
            args, msg, call_id = _tool_args(resp)
        except NemotronError as e:
            return NemotronPlan(False, attempts=n, latency_s=time.monotonic() - t0, errors=all_errors, error=str(e))
        if "_unparsable" in args:
            mapping, objects, errs = {}, [], [f"no valid {TOOL_NAME} call / JSON: {str(args['_unparsable'])[:120]}"]
        else:
            mapping, objects, errs = validate(args, detections)
        if not errs:
            plan = NemotronPlan(True, mapping, objects, str(args.get("reasoning", ""))[:400], n,
                                time.monotonic() - t0, all_errors, compare(mapping, parser_mapping))
            _CACHE[key] = plan
            return plan
        all_errors.append(errs)
        fix = "Your plan was rejected:\n- " + "\n- ".join(errs) + f"\nCall {TOOL_NAME} again with a corrected plan."
        messages.append({k: v for k, v in msg.items() if k in ("role", "content", "tool_calls")})
        messages.append({"role": "tool", "tool_call_id": call_id, "content": fix} if call_id
                        else {"role": "user", "content": fix})
    return NemotronPlan(False, attempts=len(all_errors), latency_s=time.monotonic() - t0, errors=all_errors,
                        error=f"no valid plan after {n} attempt(s): {'; '.join(all_errors[-1])}")


# ------------------------------------------------------------------ CLI (smoke test / demo)
def _synthetic_scene(seed):
    import numpy as np
    from aaltonomous.baselines.classical.config import load_config
    from aaltonomous.interface.calibration import Calibration
    from aaltonomous.scene.scene import Scene

    from .perception import ShapePerception
    from .synth import SynthRenderer, random_objects
    rng = np.random.default_rng(seed)
    scene, cal = Scene.load(), Calibration.load()
    objs = random_objects(rng, scene)
    rgb, depth = SynthRenderer(scene, cal).render(objs, rng)
    dets = ShapePerception(load_config(), scene, cal).detect(rgb, depth)
    return rgb, dets, objs


def evaluate(pause_s=2.0):
    """Exact-plan accuracy (every colour x shape resolves like the expected mapping) on tests' UNSEEN set,
    text only, with one synthetic object per colour x shape as the detections."""
    import sys
    from pathlib import Path

    from .instruction import parse_instruction
    if not configured():
        print(f"{LABEL}: not configured (set NVIDIA_API_KEY)")
        return 1
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))
    from test_instruction import UNSEEN

    class _D:
        def __init__(self, c, s):
            self.color, self.shape, self.top, self.uv = c, s, (0.3, 0.0, 0.8), (0, 0)
    dets = [_D(c, s) for c in COLORS for s in SHAPES]
    grid = [(c, s) for c in COLORS for s in SHAPES]
    n_parser = n_nemo = 0
    for text, want in UNSEEN:
        exp = [_resolve(want, c, s) for c, s in grid]
        par = parse_instruction(text).mapping
        plan = plan_sort(text, None, dets, parser_mapping=par)
        ok_p = [_resolve(par, c, s) for c, s in grid] == exp
        ok_n = plan.ok and [_resolve(plan.mapping, c, s) for c, s in grid] == exp
        n_parser += ok_p
        n_nemo += ok_n
        print(f"{'ok ' if ok_n else 'BAD'} nemotron ({plan.attempts} att) | {'ok ' if ok_p else 'BAD'} parser | {text}"
              + ("" if ok_n else f"\n      got {fmt_mapping(plan.mapping) if plan.ok else plan.error}"))
        time.sleep(pause_s)
    print(f"{LABEL}: {n_nemo}/{len(UNSEEN)} exact plans; offline parser: {n_parser}/{len(UNSEEN)}")
    return 0 if n_nemo == len(UNSEEN) else 1


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=f"{LABEL} sort plan for one head frame")
    ap.add_argument("instruction", nargs="?", default="")
    ap.add_argument("--eval", action="store_true",
                    help="score Nemotron and the offline parser on the 17 unseen paraphrases of tests/ (17 calls)")
    ap.add_argument("--synthetic", type=int, nargs="?", const=0, metavar="SEED",
                    help="render a synthetic head frame (default seed 0) and run our perception on it")
    ap.add_argument("--image", help="a head camera PNG/JPG (no detections: text + image only)")
    a = ap.parse_args(argv)
    from .instruction import parse_instruction
    if a.eval:
        return evaluate()
    rgb, dets = None, []
    if a.synthetic is not None:
        rgb, dets, objs = _synthetic_scene(a.synthetic)
        print("scene:", ", ".join(f"{o['color']} {o['shape']}" for o in objs))
    elif a.image:
        import cv2
        bgr = cv2.imread(a.image)
        if bgr is None:
            raise SystemExit(f"cannot read {a.image}")
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    parse = parse_instruction(a.instruction)
    print(f"offline parser: {fmt_mapping(parse.mapping)} ({parse.confidence})")
    print("detections:\n" + describe(dets))
    plan = plan_sort(a.instruction, rgb, dets, parser_mapping=parse.mapping)
    print(plan.summary())
    for o in plan.objects:
        print(f"  id {o['id']} -> {o['bin']}  {o['why']}")
    return 0 if plan.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
