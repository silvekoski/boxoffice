# Box Office video: build notes

- Result: `out/box-office.mp4` (copied to `aalto-humanoid/video-box-office/out/` from the build VM), 1920x1080,
  30 fps, about 91 s, burned-in captions, voice Kokoro af_heart at speed 0.95. Poster: `out/poster.png`.
- Built on a rented Verda CPU VM (CPU-TURIN.8V.32G), not on the team laptop: `rsync` this directory to the VM, then
  `sh tools/setup.sh`, `SPEED=0.95 sh tools/make_voice.sh`, `uv run tools/align_words.py`, `uv run tools/build.py`,
  `npx hyperframes render -o /tmp/box-office-raw.mp4 -q looks -f 30`, `sh tools/master.sh /tmp/box-office-raw.mp4`.
  The VM needs node 24, uv, ffmpeg and the Chromium libraries (libnss3, libgbm1, libasound2t64, ...).
- Departures from the template: `assets/rebus.js` (the logo pictograms as inline SVG, loaded by
  `tools/index.template.html`); scenes 1 and 7 use the brand blue `#2B43A6` instead of the dark background.
- Data on screen: see the table in `SCRIPT.md`. Real venue frames are Aalto's Drop 3 (Hugging Face
  `zupermiez/g1_junction_drop_3`, Apache-2.0) with our detections drawn; the sim frame is from our 2026-11-14 run.
  `assets/data/` (git-ignored) holds the copies.
- Checks: `hyperframes lint` 0 errors (the caption density warning is by design); 18 stills reviewed on two
  contact sheets; scene 3 got a title at 0.2 s (it started empty) and scene 1's first line was re-centred.
- Whisper heard "Aalto" as "Alto" and numbers as digits; captions use the script text.
- Not checked by a person yet: motion and sound. Watch it once before you submit it.
