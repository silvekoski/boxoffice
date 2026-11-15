"""Instruction parser: every training template x every colour/bin permutation, plus unseen paraphrases."""
import itertools

import pytest

from aaltonomous.interface.tasks import FIXED_INSTRUCTION, TEMPLATES, make_instruction
from aaltonomous.scene.scene import resolve_bin
from sorter.instruction import FIXED_MAPPING, parse_instruction

PERMS = list(itertools.permutations(("red", "yellow", "blue")))
BPERMS = list(itertools.permutations(("left", "center", "right")))


def fill(template, colors, bins):
    words = {f"c{i}": c for i, c in enumerate(colors)}
    words.update({f"C{i}": c.capitalize() for i, c in enumerate(colors)})
    words.update({f"b{i}": b for i, b in enumerate(bins)})
    return template.format(**words)


@pytest.mark.parametrize("ti", range(len(TEMPLATES)))
def test_all_training_templates_all_permutations(ti):
    for colors in PERMS:
        for bins in BPERMS:
            text = fill(TEMPLATES[ti], colors, bins)
            r = parse_instruction(text)
            assert r.mapping == dict(zip(colors, bins)), (text, r)
            assert r.confidence == "explicit", (text, r)


def test_make_instruction_samples():
    import numpy as np
    rng = np.random.default_rng(0)
    for _ in range(200):
        text, mapping = make_instruction("sort_language", rng)
        assert parse_instruction(text).mapping == mapping, text


def test_fixed_instruction_and_task():
    assert parse_instruction(FIXED_INSTRUCTION).mapping == FIXED_MAPPING
    assert parse_instruction("whatever", task="sort_fixed").mapping == FIXED_MAPPING


UNSEEN = [
    ("Red goes left, yellow goes in the middle, blue goes right.", {"red": "left", "yellow": "center", "blue": "right"}),
    ("Please sort: blue -> left; red -> middle; yellow -> right", {"blue": "left", "red": "center", "yellow": "right"}),
    ("Left: yellow. Centre: blue. Right: red.", {"yellow": "left", "blue": "center", "red": "right"}),
    ("I want the yellow pieces in the rightmost box and the red pieces in the leftmost box, blue in the middle one.",
     {"yellow": "right", "red": "left", "blue": "center"}),
    ("Throw all blue things into the left-hand bin, then the reds into the centre container, then yellows right.",
     {"blue": "left", "red": "center", "yellow": "right"}),
    ("The box on the right takes the red blocks; the middle box takes blue; the left box takes yellow.",
     {"red": "right", "blue": "center", "yellow": "left"}),
    ("Could you place the RED items into the CENTER bin, the BLUE items into the RIGHT bin, and the YELLOW items "
     "into the LEFT bin?", {"red": "center", "blue": "right", "yellow": "left"}),
    ("Blue belongs on the left. Yellow belongs on the right. Red belongs in the center.",
     {"blue": "left", "yellow": "right", "red": "center"}),
    ("Red and blue swap places compared to usual.", {"red": "right", "blue": "left", "yellow": "center"}),
    ("Sort as usual but swap red and yellow.", {"red": "center", "yellow": "left", "blue": "right"}),
    ("Do the opposite of the default sorting.", {"red": "right", "yellow": "center", "blue": "left"}),
    ("Red in the right bin and blue in the left bin.", {"red": "right", "blue": "left", "yellow": "center"}),
    ("Yellow objects go to the left bin. Red ones should not go into the center bin.",
     {"yellow": "left", "red": "right", "blue": "center"}),
    ("Red doesn't go left, it goes right. Blue goes left.", {"red": "right", "blue": "left", "yellow": "center"}),
    ("Everything red into the middle, everything else into the left bin.", {"red": "center", "default": "left"}),
    ("Put the cubes in the left bin, the cylinders in the center bin and the triangles in the right bin.",
     {"cube": "left", "cylinder": "center", "triangle": "right"}),
    ("Red cubes go right; all other objects go to the left bin.", {("red", "cube"): "right", "default": "left"}),
]


@pytest.mark.parametrize("text,expected", UNSEEN)
def test_unseen_paraphrases(text, expected):
    r = parse_instruction(text)
    for k, v in expected.items():
        assert r.mapping.get(k) == v, (text, r)
    # every colour that the expected mapping decides must resolve the same through the organisers' resolver
    for c in ("red", "yellow", "blue"):
        for s in ("cube", "cylinder", "triangle"):
            assert resolve_bin(r.mapping, c, s) == resolve_bin(expected, c, s), (text, c, s, r)


def test_nothing_understood_falls_back_to_fixed():
    r = parse_instruction("Do your best!")
    assert r.mapping == FIXED_MAPPING and r.confidence == "fallback"


def test_incomplete_is_not_guessed():
    r = parse_instruction("Put the red ones on the left.")
    assert r.mapping == {"red": "left"}
    assert r.bin_for("blue") is None


# Unseen phrasings checked on 2026-11-15 (the real robot's unseen instruction counts 1.5x).
NEW_PARAPHRASES = [
    ("Every red piece belongs in the box on the right; blues on the left; yellows in the middle.",
     {"red": "right", "blue": "left", "yellow": "center"}),
    ("Could you put the yellow blocks into the leftmost box, the red ones in the rightmost and the blue ones in between?",
     {"yellow": "left", "red": "right", "blue": "center"}),
    ("Blue objects belong to the first box from the left, yellow to the second and red to the third.",
     {"blue": "left", "yellow": "center", "red": "right"}),
    ("Counting from the right: red in the first box, blue in the second, yellow in the third.",
     {"red": "right", "blue": "center", "yellow": "left"}),
    ("First, put red left. Then blue right and yellow middle.", {"red": "left", "blue": "right", "yellow": "center"}),
    ("Left box: blue. Middle box: red. Right box: yellow.", {"blue": "left", "red": "center", "yellow": "right"}),
    ("Put the red ones in the box nearest your right hand, the blue ones nearest your left hand, yellow straight ahead.",
     {"red": "right", "blue": "left", "yellow": "center"}),
    ("Yellow into the left bin, the rest into the right bin.", {"yellow": "left", "red": "right", "blue": "right"}),
    ("Put the crimson ones on the right, the azure ones on the left and the golden ones in the middle.",
     {"red": "right", "blue": "left", "yellow": "center"}),
]


def test_new_unseen_paraphrases():
    from aaltonomous.scene.scene import resolve_bin
    for text, want in NEW_PARAPHRASES:
        p = parse_instruction(text, task="sort_language")
        for colour, b in want.items():
            assert resolve_bin(p.mapping, colour, None) == b, (text, colour, p.mapping)


def test_colour_blocks_mean_all_shapes_but_bare_blocks_are_cubes():
    from aaltonomous.scene.scene import resolve_bin
    p = parse_instruction("Put the yellow blocks left, the rest right.", task="sort_language")
    assert resolve_bin(p.mapping, "yellow", "cylinder") == "left"
    p = parse_instruction("Blocks go left, everything else right.", task="sort_language")
    assert resolve_bin(p.mapping, "red", "cube") == "left" and resolve_bin(p.mapping, "red", "cylinder") == "right"
