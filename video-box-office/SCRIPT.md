# Box Office: script and storyboard

Title: **Box Office - a brain for Aalto's G1 humanoid**

Length: about 2 minutes (Junction video limit 2:00). 1920x1080, 30 fps. English narration, one voice clip per scene.
The narration is the source of truth. A scene is as long as its voice clip plus 0.5 s.

Every number on screen or in the narration is in the table "Numbers and their sources" at the end.

## Style

- Template look: dark background `#0E1116`, real frames on a paper card. The first and last scenes use the Box
  Office brand blue `#2B43A6` with the rebus logo (`aalto-humanoid/brand/`).
- Colours: blue = input (an instruction, a camera frame), amber = evidence, green = a gain or a right box,
  red = an error, grey = context.
- Inter for text, JetBrains Mono for numbers. At most 7 words per line on screen.
- Voice: Kokoro af_heart at speed 0.95 (the template's 0.82 would run past two minutes).

## Real material

| Key | File (copied to `assets/data/`) | What it is |
|---|---|---|
| SIM | `/tmp/snaps/i6/head_rgbd_rgb.jpg` from the 2026-11-14 sim run | Head camera frame of Aalto's Isaac Sim scene, randomised, our policy running |
| REAL_BEFORE | Drop 3 episode 2 with the first perception detections drawn (`~/hfwork/drop3_det/ep02_det.jpg`) | Real venue frame; box flaps marked red, hands marked blue |
| REAL_AFTER | Same frame after the fixes (`~/hfwork/drop3_det8/ep02_det.jpg`) | Objects found with the right colours and shapes |

Real frames: Hugging Face `zupermiez/g1_junction_drop_3` (Aalto University, Apache-2.0).

## Scenes

### 1. Hook (about 14 s)

Narration:
> This humanoid can do a backflip. It cannot put a block in a box. We gave it a brain, and a name. Box. Off. Ice. Box Office.

Picture: brand blue. The title line "Backflips: easy. Blocks: hard." types on. At "Box. Off. Ice." the three
pictograms of the rebus land one per word. At "Box Office" the wordmark appears under them.

### 2. The task (about 20 s)

Narration:
> Three to five objects lie on the counter. Cubes, cylinders and prisms, in red, yellow and blue. Three boxes wait behind them. The robot has two minutes. A right box earns points. A wrong box costs one. So when it is unsure, it skips.

Picture: SIM on a paper card, left. Right column: chips "3 to 5 objects", "3 boxes", "120 s", then
"+ right box" green, "- wrong box" red, "0 skipped" grey, each with its words.

### 3. Language (about 16 s)

Narration:
> A person says where things go, in their own words. The blue ones in between. The first box from the left. Our parser has no templates. It turns each sentence into one box per object.

Picture: two blue instruction chips arrive with their words; an arrow from each to a green result chip
("blue → centre", "first from left → left"). A grey chip "no templates".

### 4. The real camera (about 22 s)

Narration:
> Aalto published real recordings from the venue. On those frames, the stock colour rules saw the orange boxes and the robot's hands as objects, and missed the red ones. We fixed the colours. Detections fell from one hundred thirty-two to seventy-four, about five per frame.

Picture: REAL_BEFORE on a paper card with a red tag "stock rules". At "We fixed" it crossfades to REAL_AFTER with a
green tag. A counter 132 → 74 ticks; label "detections on 15 real frames".

### 5. A tilted camera (about 16 s)

Narration:
> The camera calibration was off too. The table looked tilted by fourteen degrees. Now the robot measures the table itself, and levels it. Objects read about forty-five millimetres tall again.

Picture: a long amber line (the table) tilted 14 degrees with a red "14°" chip; it levels with an ease-in-out move;
red chip "60 to 87 mm" becomes green chip "46 to 51 mm" next to "45 mm objects".

### 6. Results (about 26 s)

Narration:
> We scored it in Aalto's simulator, on randomised scenes. Fixed sorting: ten of twenty objects, up from eight. By instruction: ten of eighteen. Not one object went into a wrong box, and the safety filter never clipped a command. On the real recordings, the robot starts moving after about one second, not up to fifty-two.

Picture: two pairs of bars (before / Box Office) for fixed and instruction with their counts; then chips
"0 wrong boxes" and "0 safety clips" in green; then "52 s → 1 s" in green.

### 7. Close (about 12 s, plus 2 s pad)

Narration:
> Box Office. Plain words in, sorted boxes out. Thanks to Aalto University and Junction.

Picture: brand blue, the full rebus poster, the line "Plain words in. Sorted boxes out." and the credits:
"Real-robot data: Aalto University (Hugging Face, Apache-2.0). Simulator and starter: Aalto aaltonomous."

## Numbers and their sources

| Number | Source |
|---|---|
| 3 to 5 objects, 3 boxes, 2 minutes, right / wrong / skipped scoring | `docs/junction/challenges/11-aalto-university-aaltonomous-humanoid.md`; `upstream/aaltonomous/docs/participants/RULES_AND_SCORING.md` |
| 132 → 74 detections on 15 real frames, about 5 per frame | `aalto-humanoid` commit d4b8580c message and the hq log 2026-11-15; the same run is reproduced by `~/hfwork/real_perception.py` (74 at commit d4b8580c) |
| table tilted ~14 deg; object tops 60 to 87 mm before, 46 to 51 mm after | commit e76ee121 message; `sorter/selfcal.py` docstring |
| Fixed sorting 10/20 (Box Office v9) vs 8/20 (v1); instruction 10/18 vs 12/18 (v1) | `aalto-humanoid/results/sim-dr-v9-2026-11-15/README.md` |
| 0 wrong boxes, 0 clipped commands | same file ("All trials: 0 clipped commands, gate pass, no object in a wrong box") |
| first move after ~1 s instead of up to 52 s | commit 0461a215 message (real frames: first plan 18-52 s → ~1 s) |
