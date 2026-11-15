# v3 vs v1 on the same randomised scenes, 2026-11-15

v3 = FacePlanner (the organisers' oracle planner on our detections) + real-camera perception fixes (commit d4b8580c),
image `sha256:ee48c4d5a17d7a414201f8373a4ef441ac4e401c83de47cb5dbbfa842d7ea430`. Same sim (`AALTO_DR=train`), same
seeds as v1 (`../sim-dr-2026-11-14/`), so the same scenes. Verda 8x RTX PRO 6000, 8 sims in parallel; the run was cut
after 13 trials because of the team's Verda budget. Raw lines: `trials.log`; runner logs: `i*_episode_*.jsonl`.

| Task | Matched trials | v1 objects correct | v3 objects correct | v3 clips / gate |
|---|---|---|---|---|
| sort_fixed | 6 (seeds 1000, 1001, 1003, 1004, 1006, 1009) | 9/25 | **13/25** | 0 / all pass |
| sort_language | 7 (seeds 1000, 1001, 1003, 1004, 1006, 1007, 1009) | 16/24 (score 32/48) | 15/24 (score 30/48) | 0 / all pass |

Per seed (v1 -> v3): fixed 1000 2->2/3, 1001 1->2/5, 1003 3->3/3, 1004 0->1/5, 1006 1->1/4, 1009 2->4/5;
language 1000 2->2/3, 1001 2->2/3, 1003 3->3/4, 1004 2->2/3, 1006 3->3/3, 1007 2->2/4, 1009 2->1/4.
Still no wrong box and nothing knocked off.

Perception against the sim's ground truth (`sim/perception_diag.py`, 20 DR seeds, `diag_v3_noselfcal.log`): 82/82
objects found, colour 82/82, 0 false positives; xy error median 12-13 mm, p90 ~24 mm, the same for every object of a
scene: the DR head-pose jitter (+-1 cm / +-1 deg). Full self-calibration (plane + box fit every frame,
`diag_selfcal_full.log`) was mixed and lost every object in one scene, so the image uses the "gross" mode only: a
counter-plane correction when the calibration is clearly wrong (>= 4 deg / 2 cm). It never triggers in the sim and
fixes the real Drop 3 frames (counter tilted ~14 deg under calibration v1).

v5 = v3 + gross self-calibration + in-box margin -1.5 cm (commit after e76ee121), image
`sha256:5294bbc95e385d426b68489e5b740d311612066c1014879c10eed620b84cfb78`: replay pre-check pass (632 Hz, 0 errors);
not sim-scored (the plane correction cannot trigger at sim jitter; tests/test_selfcal.py).
