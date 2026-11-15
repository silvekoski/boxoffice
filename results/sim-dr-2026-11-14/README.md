# Sim eval of our image on randomised scenes, 2026-11-14/15

First sim scores of **our** policy. The 2026-11-13 numbers in `../sim-2026-11-13/` are the organisers' privileged
oracle, not our image: upstream `evaluate.py` checks `--policy` (default `oracle`) before `--container`, and that
run's `eval.log` shows `policy: {'name': 'oracle'}`. Always pass `--policy ws://localhost:<port>` with `--container`.

- Image `junction-sorter:v1`, id `sha256:abd325c86ae7e8be7ccd52fcdbc8d302085503b48041a8b483cf8f722b21ba13`
  (built from 777a15f on the VM; this is the image to submit). Metadata name `junction-sorter` in every run.
- Sim: bare-metal Isaac (`sim/setup_fixloop.sh`), `AALTO_DR=train` (lighting, textures, colours, poses randomised),
  upstream 36daf5b. Verda 8x RTX PRO 6000, 8 sim instances in parallel (one per GPU), 3 trials each, seeds 1000-1011.
- Raw: `i<N>_junction_<task>_train_<ts>.json` (evaluate's eval.json: per-object outcomes, DR params), `trials.log`.

| Task | Trials | Objects correct | Score | Wrong box | Knocked off | Left on counter | Gate |
|---|---|---|---|---|---|---|---|
| sort_fixed | 12 | 17/48 (35 %) | 17/48, mean +1.42 / trial | 0 | 0 | 31 | PASS 12/12: 0 clips, >= 29.97 Hz |
| sort_language | 12 | 25/43 (58 %) | 50/86, mean +4.17 / trial | 0 | 0 | 18 | PASS 12/12: 0 clips, >= 29.98 Hz |

By shape (both tasks): cube 21/28 correct, cylinder 13/34, triangle 8/29.

What it says:
- **No penalties at all.** 0 wrong boxes and 0 objects off the counter in 91 objects: perception, colour under
  randomised lighting and the instruction mapping hold up; the skip-rather-than-guess rule works.
- **Every miss is an object left on the counter, mostly cylinders and triangles**: the pinch grasp slips, the policy
  retries (max 2 attempts per object) and then skips it. Trials with many round objects run to ~115 s.
- Next lever is the grasp on cylinders and prisms (and grasp verification from `hand_q` before the carry), not
  perception or the parser. Faster picks matter second.
- Sim ran at RTF ~0.11 with 8 instances on one VM (CPU-bound); command rate in sim time stayed 30 Hz.
