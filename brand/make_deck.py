"""Box Office thumbnail (1280x720) and pitch deck (16:9 SVG pages -> one PDF with rsvg-convert).

    python3 brand/make_deck.py && rsvg-convert -f pdf -o brand/box-office-deck.pdf brand/deck/slide-*.svg
Numbers: aalto-humanoid/results/sim-dr-v9-2026-11-15/README.md and the commits named in video-box-office/SCRIPT.md.
"""
import base64
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BLUE, DEEP, L1, L2, L3, RED, GREEN, INK, GREY = "#2B43A6", "#1E2F78", "#E4EAFD", "#B8C5F6", "#8EA2EE", "#E9604D", "#3FBF8F", "#FFFFFF", "#C9D2F2"
FONT = "Inter, Helvetica Neue, DejaVu Sans, Arial, sans-serif"
MONO = "JetBrains Mono, DejaVu Sans Mono, monospace"


def img(path, x, y, w, h):
    b = base64.b64encode(Path(path).read_bytes()).decode()
    return f'<image x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="xMidYMid slice" href="data:image/jpeg;base64,{b}"/>'


def rebus(x, y, s):
    """The three pictograms (Box, Off, Ice) at scale s, top-left x, y (drawing space 30..1130 x 320..700)."""
    return f'''<g transform="translate({x} {y}) scale({s}) translate(-30 -320)">
  <defs><clipPath id="bf{int(x)}{int(y)}"><path d="M92 470 L392 470 L372 700 L112 700 Z"/></clipPath></defs>
  <path d="M120 470 L170 395 L314 395 L364 470 Z" fill="#5B72D6"/><path d="M92 470 L40 410 L120 395 L170 470 Z" fill="{L3}"/>
  <path d="M392 470 L444 410 L364 395 L314 470 Z" fill="{L3}"/>
  <g clip-path="url(#bf{int(x)}{int(y)})" fill="{L2}">''' + "".join(f'<rect x="80" y="{yy}" width="330" height="20"/>' for yy in (470, 506, 542, 578, 614, 650)) + f'''<rect x="80" y="686" width="330" height="14"/></g>
  <rect x="216" y="330" width="52" height="52" rx="4" fill="{RED}" transform="rotate(-12 242 356)"/>
  <path d="M556 420 A110 110 0 1 0 684 420" fill="none" stroke="#FFFFFF" stroke-width="40" stroke-linecap="round"/>
  <rect x="600" y="360" width="40" height="150" rx="20" fill="#FFFFFF"/>
  <path d="M960 380 L1080 440 L960 500 L840 440 Z" fill="{L1}"/><path d="M840 440 L960 500 L960 650 L840 590 Z" fill="{L2}"/>
  <path d="M1080 440 L960 500 L960 650 L1080 590 Z" fill="{L3}"/><path d="M870 470 L900 485 L900 560 L870 545 Z" fill="#FFFFFF" opacity="0.85"/>
  <circle cx="1010" cy="430" r="9" fill="#FFFFFF"/><ellipse cx="960" cy="668" rx="150" ry="20" fill="#5B72D6" opacity="0.8"/>
  <path d="M1102 560 C1102 560 1086 586 1086 598 A16 16 0 0 0 1118 598 C1118 586 1102 560 1102 560 Z" fill="{L1}"/>
</g>'''


def page(body, w=1920, h=1080, bg=BLUE):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
<defs><filter id="g" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7" result="n"/>
<feColorMatrix in="n" type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.06 0"/><feComposite in2="SourceGraphic" operator="in"/></filter></defs>
<rect width="{w}" height="{h}" fill="{bg}"/><rect width="{w}" height="{h}" fill="#fff" filter="url(#g)"/>
{body}</svg>'''


def t(x, y, s, size=40, fill=INK, weight=400, anchor="start", font=FONT, ls=0):
    return f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" letter-spacing="{ls}">{s}</text>'


def head(n, title, kicker):
    return t(120, 150, kicker.upper(), 28, L2, 400, font=MONO, ls=4) + t(120, 240, title, 76, INK, 700, ls=-2) + t(1800, 1020, f"{n:02d}", 28, L3, font=MONO, anchor="end") + \
        rebus(120, 975, 0.06) + t(200, 1020, "Box Office", 26, L2, 600)


def chip(x, y, w, s, col=L2, fill="none", size=36, txt=INK):
    return f'<rect x="{x}" y="{y}" width="{w}" height="70" rx="14" fill="{fill}" stroke="{col}" stroke-width="3"/>' + t(x + 26, y + 47, s, size, txt)


def card(path, x, y, w, h):
    return f'<rect x="{x - 10}" y="{y - 10}" width="{w + 20}" height="{h + 20}" rx="10" fill="#F4F1EA"/>' + img(path, x, y, w, h)


V = ROOT / "video-box-office/assets/data"
slides = []
# 1 title
slides.append(page(rebus(330, 260, 1.15) + t(960, 175, "‘Box - Off - Ice’", 96, INK, 700, "middle", ls=-3)
                   + t(960, 830, "Box Office", 120, INK, 700, "middle", ls=-4)
                   + t(960, 905, "A brain for Aalto’s G1 humanoid: plain words in, sorted boxes out.", 40, L1, 400, "middle")
                   + t(960, 1010, "JUNCTION 2026 · AALTONOMOUS HUMANOID · AALTO UNIVERSITY", 26, L2, 400, "middle", MONO, 4)))
# 2 problem
slides.append(page(head(2, "Backflips are easy. Blocks are hard.", "The problem")
                   + card(V / "sim_head.jpg", 120, 320, 800, 600)
                   + t(1040, 360, "Aalto’s Unitree G1 must sort 3–5 objects", 40) + t(1040, 412, "(cubes, cylinders, prisms; red, yellow, blue)", 32, GREY)
                   + t(1040, 480, "into 3 identical boxes, in 2 minutes,", 40) + t(1040, 532, "by a fixed rule or a free-text instruction.", 40)
                   + chip(1040, 610, 340, "+ right box", GREEN) + chip(1400, 610, 360, "− wrong box", RED)
                   + chip(1040, 700, 340, "0 skipped", L2)
                   + t(1040, 840, "Real-robot result is 40% of the judging.", 36, L1) + t(1040, 890, "The unseen instruction counts 1.5×.", 36, L1)))
# 3 approach
steps = [("Head RGB-D", "colour + depth", L2), ("Perception", "colour, shape, table self-calibration", L2),
         ("Language", "template-free parser → box per object", L2), ("Planner", "Aalto’s planner + face-aligned grasps", L2),
         ("Safety", "every trajectory pre-checked, 30 Hz", GREEN)]
body = head(3, "One explainable pipeline", "Our approach")
for i, (a, b, c) in enumerate(steps):
    y = 300 + i * 116
    body += f'<rect x="120" y="{y}" width="560" height="92" rx="16" fill="{DEEP}" stroke="{c}" stroke-width="3"/>' + t(150, y + 60, a, 44, INK, 700) + t(720, y + 60, b, 38, L1)
    if i < len(steps) - 1:
        body += f'<path d="M400 {y + 92} L400 {y + 116}" stroke="{L3}" stroke-width="4"/>'
body += t(120, 935, "Unsure? Skip it: a wrong box costs a point, an empty one costs nothing.", 34, L1)
slides.append(page(body))
# 4 language
rows = [("“the blue ones in between”", "blue → centre"), ("“the first box from the left”", "→ left box"),
        ("“cubes go left, everything else right”", "cube → left, rest → right"), ("“same as usual, but swap blue and yellow”", "yellow → right, blue → centre")]
body = head(4, "Say it in your own words", "Language")
for i, (q, a) in enumerate(rows):
    y = 330 + i * 130
    body += chip(120, y, 900, q, L2, DEEP, 36) + f'<path d="M1050 {y + 35} L1150 {y + 35} M1130 {y + 18} L1152 {y + 35} L1130 {y + 52}" stroke="{L3}" stroke-width="5" fill="none"/>' + chip(1180, y, 620, a, GREEN, "none", 36)
body += t(120, 930, "No templates. 8 training templates × 36 permutations, 200 sampled and 26 unseen phrasings in the tests.", 32, L1)
slides.append(page(body))
# 5 real camera
slides.append(page(head(5, "The real camera is not the sim", "Real venue frames")
                   + card(V / "real_before.jpg", 120, 330, 760, 570) + card(V / "real_after.jpg", 1040, 330, 760, 570)
                   + chip(140, 350, 360, "stock colour rules", RED, DEEP, 32) + chip(1060, 350, 220, "Box Office", GREEN, DEEP, 32)
                   + t(120, 965, "Stock rules saw the orange boxes and the robot’s hands as objects and missed the red ones.", 32, L1)
                   + t(1800, 150, "132 → 74 detections on 15 frames", 32, GREEN, 700, "end", MONO)))
# 6 tilt
body = head(6, "A tilted camera, levelled from the table", "Self-calibration")
body += f'<g transform="rotate(-14 520 640)"><line x1="160" y1="640" x2="880" y2="640" stroke="{RED}" stroke-width="10" stroke-linecap="round" opacity="0.6"/></g>'
body += f'<line x1="160" y1="640" x2="880" y2="640" stroke="{GREEN}" stroke-width="10" stroke-linecap="round"/>'
for k, c in enumerate((RED, "#4C9BE8", "#E8C547")):
    body += f'<rect x="{330 + k * 150}" y="575" width="65" height="65" rx="4" fill="{c}"/>'
body += t(1040, 470, "Under Aalto’s current calibration file", 38) + t(1040, 522, "the real table reads 14° tilted.", 38) \
    + chip(1040, 590, 470, "tops read 60–87 mm", RED) + chip(1040, 690, 470, "tops read 46–51 mm", GREEN) + t(1040, 820, "objects are 45 mm tall", 32, L2, font=MONO) \
    + t(120, 930, "The robot fits the table plane in each frame and corrects only a clearly wrong calibration.", 32, L1)
slides.append(page(body))
# 7 results
body = head(7, "Results on randomised sim scenes", "Evidence")
bars = [("fixed sorting", 8, 20, 10, 20), ("by instruction", 12, 18, 10, 18)]
for i, (name, a, an, b, bn) in enumerate(bars):
    x0 = 160 + i * 460
    for j, (v, n, c) in enumerate(((a, an, "#5A6475"), (b, bn, GREEN))):
        h = int(v / n * 420)
        body += f'<rect x="{x0 + j * 170}" y="{860 - h}" width="150" height="{h}" rx="8" fill="{c}"/>' + t(x0 + j * 170 + 75, 840 - h, f"{v}/{n}", 44, INK if j == 0 else GREEN, 700, "middle", MONO)
    body += t(x0 + 160, 910, name, 34, L1, 400, "middle")
body += f'<line x1="140" y1="860" x2="1060" y2="860" stroke="{L3}" stroke-width="2"/>' + t(160, 330, "■ first version   ", 28, GREY) + t(420, 330, "■ Box Office", 28, GREEN)
body += chip(1180, 380, 520, "0 wrong boxes", GREEN) + chip(1180, 480, 520, "0 safety clips", GREEN) + chip(1180, 580, 620, "real first move 52 s → 1 s", GREEN)
body += t(1180, 740, "Same 10 scenes per version (seeds 1000–1004).", 30, L1) + t(1180, 790, "Run-to-run variance is large.", 30, L1)
slides.append(page(body))
# 8 limits and next
body = head(8, "What limits us, what comes next", "Honest scope")
items = [("Grasps slip on round and prism objects", "the sim’s head-pose jitter moves every object 12–25 mm", RED),
         ("Real calibration is provisional", "we correct the table tilt; x/y still need the boxes or tags", RED),
         ("Next: wrist-camera check before closing", "re-centre on the object from 8 cm above", L2),
         ("Next: grasp verification", "fingers stopped early = object held, else re-look", L2)]
for i, (a, b, c) in enumerate(items):
    y = 340 + i * 145
    body += f'<circle cx="140" cy="{y}" r="14" fill="{c}"/>' + t(180, y + 14, a, 42, INK, 700) + t(180, y + 66, b, 32, L1)
slides.append(page(body))
# 9 submission
slides.append(page(rebus(1330, 560, 0.42) + head(9, "The submission", "Box Office")
                   + t(120, 360, "Docker image (linux/amd64, CUDA 12.8 base, CPU policy):", 34, L1)
                   + t(120, 420, "ghcr.io/silvekoski/aalto-sorter", 40, INK, 700, font=MONO)
                   + t(120, 470, "@sha256:db36b761d5e0…a0bf9781", 32, L2, font=MONO)
                   + t(120, 570, "Organisers’ pre-check: 680 commands/s (gate 27), 0.5 s startup", 34, L1)
                   + t(120, 630, "69 tests, incl. real venue frames and 26 unseen phrasings", 34, L1)
                   + t(120, 690, "Source: aalto-humanoid/ · video: 1:31 explainer", 34, L1)
                   + t(120, 860, "Plain words in. Sorted boxes out.", 64, INK, 700, ls=-1)))
for i, s in enumerate(slides, 1):
    (HERE / "deck" / f"slide-{i:02d}.svg").write_text(s)
# thumbnail 1280x720
thumb = page(rebus(230, 150, 0.75) + t(640, 600, "Box Office", 110, INK, 700, "middle", ls=-4)
             + t(640, 665, "A brain for Aalto’s G1 humanoid", 38, L1, 400, "middle"), 1280, 720)
(HERE / "box-office-thumbnail.svg").write_text(thumb)
print(len(slides), "slides")
