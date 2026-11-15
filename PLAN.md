# Aaltonomous Humanoid: plan

Challenge brief: `docs/junction/challenges/11-aalto-university-aaltonomous-humanoid.md`. Organisers' rules,
interface and submission contract: `upstream/aaltonomous/docs/participants/` (fetch with `scripts/fetch_upstream.sh`).
Final submission: Sunday 15.11 (organisers announce the time; Junction deadline 10:00 Helsinki).

## What decides the result

| Weight | What | What it means for us |
|---|---|---|
| Gate | Sim gate on the held-out variant: 0 clipped steps, ≥ 27 Hz command rate (also against our own latency), no crash | Every trajectory is pre-checked against the real safety filter; planning runs in a thread, act() never blocks |
| Finalist | Mean sim score on the held-out variant (other textures, light, poses, camera jitter) | Perception must not depend on exact sim colours; no tuning to one scene |
| 40 % | Real-robot score, 3 episodes: sort_fixed, sort_language (training template), sort_language **unseen instruction ×1.5** | Language rung is worth +2 per object and the unseen one counts 1.5×: the instruction parser is high leverage |
| 25 % | Generality | Parser with no templates, shape-aware mapping, robust to blank frames and depth holes |
| 20 % / 15 % | Originality / presentation | Explainable pipeline; show the parse and the per-object plan live |

Points per object: correct +1 (fixed) / +2 (language), wrong −1, knocked off −1, left 0. So a skipped object is
better than a guessed one, and a dropped object near the bin costs nothing unless it falls off the counter.

## Approach: modular and scripted, on top of the organisers' classical stack

End-to-end learning is not realistic in 36 h with ~20 real demos per rung, and the finals reward robustness on
an unseen scene. The organisers' classical baseline already sorts 76–82 % of objects in the nominal sim at
30 Hz with 0 clips (their FAQ, 2026-11-11), but only does rung 1, ignores shape and drops triangles. We reuse its
planner, IK and safety pre-check unchanged and replace or extend the parts that decide the score:

```
head RGB + depth ──> HSV blobs + depth (upstream) ──> top-face points (pelvis frame)
                                                      ├─> top centre (upstream)  ──> grasp point
                                                      └─> shape (ours: square / disc / triangle fill)
instruction ──> parser (ours, offline) ──> mapping {colour | shape | (colour, shape) | default -> bin}
detection + resolve_bin(mapping) ──> planner (upstream: IK, Cartesian waypoints, 30 Hz, ≤ 0.97 rad/s,
                                     counter / bin clearances, dry run through SafetyFilter) ──> chunks
```

Built (slice 1, this commit):

1. **Instruction parser** (`sorter/instruction.py`): no templates. Synonym tables (centre/middle, reds,
   leftmost, the box on the right, cubes/blocks, prisms ...), unit splitting at punctuation and conjunctions,
   merging ("red and blue go left", "Left: red", "..., it goes right"), negated bins as exclusions,
   modifiers ("as usual", "reverse", "swap red and blue", "swap the left and right bins"), one-to-one
   completion, and fixed mapping as fallback. Output uses the scorer's own `resolve_bin` keys, so shape
   instructions ("cubes go left", "red cubes right, everything else left") work end to end.
   Tests: all 8 training templates × 36 permutations, 200 sampled instructions, 17 unseen paraphrases.
2. **Shape-aware perception** (`sorter/perception.py`): classifies each top face from its metric point cloud;
   86/87 correct on synthetic frames with depth noise and holes. Gives triangle yaw for a later edge grasp.
3. **Policy** (`sorter/policy.py`): the upstream state machine with our mapping and perception; re-looks on a
   blank camera frame instead of ending the episode; confirms an empty scene with a second look; skips objects
   the instruction does not cover.
4. **Triangle-aligned grasp** (`sorter/planner.py`): for prisms the planner first tries the finger direction
   along a face normal closest to forward (one contact on a flat face), then the upstream hints. Untested in
   the sim yet; `SORTER_TRIANGLE_ALIGN=off|face|vertex` switches it for an A/B run.
5. **Server + image** (`sorter/server.py`, `Dockerfile`): the organisers' protocol on :8000, threaded planning.
   Replay at ≥ 27 Hz and a full runner episode on the mock backend with 0 clips are unit tests.

## Sim results (2026-11-15, randomised scenes `AALTO_DR=train`, image `junction-sorter:v1`)

12 trials per task, seeds 1000–1011, 8 sims in parallel on Verda 8x RTX PRO 6000. Raw output and analysis:
`results/sim-dr-2026-11-14/`.

| Task | Objects correct | Score (mean) | Wrong box / knocked off | Left on counter | Gate |
|---|---|---|---|---|---|
| sort_fixed | 17/48 (35 %) | +1.42 / trial (35 % of max) | 0 / 0 | 31 | PASS 12/12: 0 clips, 30 Hz |
| sort_language | 25/43 (58 %) | +4.17 / trial (58 % of max) | 0 / 0 | 18 | PASS 12/12: 0 clips, 30 Hz |

By shape: cube 21/28, cylinder 13/34, triangle 8/29. No penalties in 91 objects; every miss is a failed grasp
(retried, then skipped). The grasp on round and prism objects is the main lever.

The 2026-11-13 table that used to stand here (11/12, 10/11) was the organisers' privileged **oracle**, not our
image: upstream `evaluate.py` takes `--policy` (default `oracle`) before `--container`. `sim/run_eval.sh` and
`sim/par_eval.sh` now pass `--policy ws://localhost:<port>` and fail when the run's policy name is `oracle`.

## Next slices (in order of expected points)

1. ~~Randomised scenes~~: done, see above.
2. **Cylinder and triangle grasp** (all our misses in the DR run): the pinch slips on prisms and cylinders. Use `shape_yaw` to align the
   thumb–finger axis across two flat faces (edge-on pinch), or push the prism into the bin with a scoop.
3. **Speed**: ~10–20 s per pick against 120 s for up to 5 objects. Plan the next object while the current one is
   carried; use both arms at once on objects for opposite side bins; skip the full home return when the next
   object is reachable from the retreat pose.
4. **Robust colour**: HSV ranges tuned on the real Drop 1 images and on DR renders; fall back to adaptive
   thresholds (k-means in Lab on the mat region) when a fixed range finds nothing. Use the wrist cameras to
   verify a grasp (object between the fingers) and retry before carrying.
5. **Grasp verification** from `hand_q` (fingers stopped early = object held) and a re-look after each drop.
6. **Parser stretch**: optional LLM fallback only if confidence is "fallback" and a network exists (finals
   have none guaranteed, so the offline parser stays primary).
7. **Rung 3** (insert through lid holes) only if 1–5 are solid.

## Real-robot data (Hugging Face drops, links on Discord)

- **Drop 0** (raw teleop demos, LeRobot v3.0 with head depth): `meta/aalto_episodes.jsonl` has each episode's
  layout (colour, shape, mat pose) and instruction, so the first frame of every episode is a labelled real test
  case: run perception on it and measure position error, missed objects and shape accuracy against the layout
  (a `tests/` fixture once downloaded); measure real depth holes on the 45 mm objects. The `task` strings are
  real rung-2 instructions: add them to the parser tests.
- **Drop 1** (venue lighting, empty-scene RGB-D, depth noise on our objects): re-tune HSV ranges and the
  `perception.xy_offset` head-extrinsics correction; build a depth-noise model for the synthetic tests.
- Demos also give real Dex3 closing postures on these objects: compare with `hand.closed` and adjust the squeeze.
- Calibration updates (versioned) change `calibration.yaml`: bump `UPSTREAM_REV`, rerun tests, rebuild the image.

## Risks

| Risk | Mitigation |
|---|---|
| Sim install: no sim image tarball for us (link only on Discord) | Bare-metal `setup_instance.sh` on a Verda L40S; its pip constraints conflict with isaacsim 6.2, `sim/setup_fixloop.sh` unpins them automatically |
| Held-out textures/lighting break HSV thresholds | DR training variant, Drop 1 tuning, adaptive fallback (slice 4) |
| Calibration error on the real robot (provisional extrinsics) | `xy_offset` and per-arm offsets from Drop 1 / AprilTag data; grasp verification and retry |
| Triangles slip | Edge-aligned grasp from `shape_yaw` (slice 2) |
| 120 s is too short for 5 objects | Pipelining and two-arm picks (slice 3); order by nearest bin; skip what cannot finish |
| Unseen instruction phrasing | Template-free parser with tests on paraphrases; skip rather than guess when unsure |
| Upstream changes during the event | Pinned `UPSTREAM_REV`; our code subclasses instead of forking |
