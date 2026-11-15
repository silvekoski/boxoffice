# Submitted image: v9, scored on the same DR scenes as v1 (2026-11-15)

v9 = v3's sim-proven grasp behaviour (FacePlanner with the oracle's 75 deg face directions, upstream attempts and box
margin) + real-robot fixes that are inert in the sim: gated table-plane self-calibration (triggers only at >= 4 deg /
2 cm; did not trigger on any sim scene, checked on seed 1004), near-box objects planned last, black head frames
re-looked, parser fixes. Image `sha256:f6370191d5ebc8dabb6b2d76e8643463e561bb2179bb8f1aedab814f1834264c`, pushed as
`ghcr.io/silvekoski/aalto-sorter@sha256:db36b761d5e0a9c5e755065ac7ca3b962eaea851f25b7b6e2f2a90a3a0bf9781`.
Sim: `AALTO_DR=train`, seeds 1000-1004, two instance sims on one RTX PRO 6000 (`sim/par_eval.sh 5 1`).

| Task | v1 | v7 | v8 | **v9** |
|---|---|---|---|---|
| sort_fixed (5 trials) | 8/20 | 10/20 | 2/12 (3 trials, stopped) | **10/20** |
| sort_language (5 trials) | 12/18 | 7/18 | 4/11 (3 trials, stopped) | **10/18** |

All trials: 0 clipped commands, gate pass, no object in a wrong box. Per seed (v9): fixed 2/3, 1/5, 4/4, 3/3, 0/5;
language 2/3, 1/3, 4/5, 3/4, 0/3. Seed 1004 has the largest DR head-pose error (23-33 mm on every object) and every
version struggles there. Run-to-run variance on the same seed is large, so v1, v3 and v9 are level within noise; v9 is
chosen for the real-robot fixes. v7 lost prisms with a 45 deg face-direction limit; v8 also dropped extra attempts and
counted attempts across drift, both worse. Raw lines: `trials.log`, evaluate output: `i0_eval.json`, `i1_eval.json`.
