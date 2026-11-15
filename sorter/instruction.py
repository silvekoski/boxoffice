"""Free-text sorting instruction -> target-bin mapping, deterministic and offline (no network in the finals).

    r = parse_instruction("Sort the objects: red into right, blue into left, yellow into center.")
    r.mapping      # {"red": "right", "blue": "left", "yellow": "center"}
    r.confidence   # "explicit" | "inferred" | "fallback"

The mapping uses the keys of `aaltonomous.scene.scene.resolve_bin` (the organisers' scorer): a colour, a shape,
a (colour, shape) tuple, or "default" (everything else). The most specific key wins.

How it works (no templates):
  1. Lowercase, tokenise into words; tag colour / shape / bin / negation / "rest" / modifier words via synonym
     tables (centre = center = middle, reds, cubes, prisms, the one on the left, ...).
  2. Split into units at sentence punctuation, commas, "and", "then", "while" ... .
  3. Merge units that only make sense together: "Red and blue go left" (colour-only unit shares the next unit's
     bin), "Left: red" (bin-only unit + subject-only unit), "Red doesn't go left, it goes right" (bin-only unit
     refers back to the last subject).
  4. Inside a unit: one bin -> every subject goes there; n subjects and n bins -> paired in order (covers both
     "red to left" and "the left bin is for red"); a negated bin ("not into the left bin") becomes an exclusion.
  5. Global modifiers when nothing explicit overrides them: "as usual" / "default" = the fixed rung-1 mapping,
     "reverse" / "opposite" = mirrored, "swap red and blue" / "swap the left and right bins".
  6. Completion: rung 2 maps colours to bins one-to-one, so a single colour left over gets the single bin left
     over, and exclusions that leave one bin decide it. Marked "inferred".
  7. Nothing understood -> the fixed mapping, marked "fallback".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

COLORS = ("red", "yellow", "blue")
BINS = ("left", "center", "right")
SHAPES = ("cube", "cylinder", "triangle")
FIXED_MAPPING = {"red": "left", "yellow": "center", "blue": "right"}

_COLOR = {
    "red": "red", "reds": "red", "reddish": "red", "crimson": "red", "scarlet": "red",
    "yellow": "yellow", "yellows": "yellow", "yellowish": "yellow", "golden": "yellow", "gold": "yellow",
    "blue": "blue", "blues": "blue", "bluish": "blue", "navy": "blue", "azure": "blue",
}
_BIN = {
    "left": "left", "leftmost": "left", "lefthand": "left", "leftside": "left",
    "center": "center", "centre": "center", "middle": "center", "central": "center", "mid": "center",
    "centermost": "center", "centremost": "center", "midmost": "center",
    "right": "right", "rightmost": "right", "righthand": "right", "rightside": "right",
}
_SHAPE = {
    "cube": "cube", "cubes": "cube", "cubic": "cube", "block": "cube", "blocks": "cube", "square": "cube",
    "squares": "cube", "cuboid": "cube", "cuboids": "cube",
    "cylinder": "cylinder", "cylinders": "cylinder", "cylindrical": "cylinder", "round": "cylinder",
    "circle": "cylinder", "circles": "cylinder", "circular": "cylinder", "disc": "cylinder", "disk": "cylinder",
    "discs": "cylinder", "disks": "cylinder", "puck": "cylinder", "pucks": "cylinder", "tube": "cylinder",
    "triangle": "triangle", "triangles": "triangle", "triangular": "triangle", "prism": "triangle",
    "prisms": "triangle", "wedge": "triangle", "wedges": "triangle", "pyramid": "triangle", "pyramids": "triangle",
}
_NEG = {"not", "never", "nor", "neither", "except", "but", "avoid", "without", "dont", "doesnt", "isnt", "arent",
        "shouldnt", "mustnt", "wont", "cant", "cannot"}
_NEG_STRONG = _NEG - {"but", "except", "without"}       # 'but'/'except' only negate what directly follows
_REST = {"rest", "remaining", "remainder", "else", "other", "others", "everything", "anything", "all", "leftover",
         "leftovers", "any"}
_PRONOUN = {"it", "they", "them", "those", "these", "ones", "one", "that"}
_FIXED = {"usual", "usually", "default", "standard", "normal", "normally", "fixed", "always", "regular", "original"}
_REVERSE = {"reverse", "reversed", "opposite", "mirror", "mirrored", "inverted", "invert", "backwards", "flipped"}
_SWAP = {"swap", "swapped", "switch", "switched", "exchange", "exchanged", "interchange", "trade", "flip"}
_SPLIT_WORDS = {"and", "then", "while", "whereas", "also", "plus", "afterwards", "next", "finally", "lastly"}
_SPLIT_PUNCT = set(".;!?,:\n")


@dataclass
class Mention:
    kind: str          # color | bin | shape | neg | rest | pronoun
    value: str
    pos: int           # token index
    negated: bool = False


@dataclass
class ParseResult:
    mapping: dict
    confidence: str                    # explicit | inferred | fallback
    notes: list = field(default_factory=list)
    exclusions: dict = field(default_factory=dict)

    def bin_for(self, color, shape=None):
        for k in ((color, shape), color, shape, "default"):
            if k is not None and k in self.mapping:
                return self.mapping[k]
        return None

    def color_mapping(self):
        """colour -> bin for the three colours (shape-agnostic view; None if unknown)."""
        return {c: self.bin_for(c) for c in COLORS}


_ORD = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2, "last": 2}


def _ordinals(t):
    """'first box from the left' -> left, 'the second' -> center ... Only when an anchor ('from the left/right',
    'counting from the right') is present, so 'First, put red left' keeps its sequencing meaning."""
    m = re.search(r"\b(?:from|counting from|starting from|starting at)\s+(?:the\s+)?(left|right)\b", t)
    if not m:
        return t
    order = list(BINS) if m.group(1) == "left" else list(reversed(BINS))
    t = re.sub(r"\b(?:from|counting from|starting from|starting at)\s+(?:the\s+)?(?:left|right)\b", " ", t)

    def rep(mm):
        return " " + order[_ORD[mm.group(1)]] + " "
    return re.sub(r"\b(first|1st|second|2nd|third|3rd|last)\b(?:\s+(?:box|bin|one|container))?", rep, t)


def _tokens(text):
    t = text.lower().replace("’", "'")
    t = re.sub(r"(\w)n't\b", r"\1nt", t)                  # don't -> dont, doesn't -> doesnt
    t = re.sub(r"\b(left|right)[\s-]+(hand|side)\b", r"\1\2", t)  # left-hand / left side -> lefthand
    t = re.sub(r"\b(left|right|centre|center)[\s-]+most\b", r"\1most", t)
    # "yellow blocks / pieces" = the yellow objects (the brief calls all objects blocks); bare "blocks" stays a shape
    t = re.sub(r"\b(" + "|".join(_COLOR) + r")\s+(?:blocks?|pieces?|items?|things?)\b", r"\1 ones", t)
    t = re.sub(r"\b(?:in\s+)?between\b", " center ", t)
    t = _ordinals(t)
    out = []
    for m in re.finditer(r"[a-z]+|[.;!?,:\n]", t):
        out.append(m.group(0))
    return out


def _units(tokens):
    """Split the token list into units; returns a list of lists of (index, token)."""
    units, cur = [], []
    for i, tok in enumerate(tokens):
        if tok in _SPLIT_PUNCT or tok in _SPLIT_WORDS:
            if cur:
                units.append(cur)
            cur = []
            continue
        cur.append((i, tok))
    if cur:
        units.append(cur)
    return units


def _mentions(unit):
    ms, neg_pending = [], False
    for i, tok in unit:
        if tok in _NEG:
            neg_pending = True
            continue
        kind = value = None
        if tok in _COLOR:
            kind, value = "color", _COLOR[tok]
        elif tok in _BIN:
            kind, value = "bin", _BIN[tok]
        elif tok in _SHAPE:
            kind, value = "shape", _SHAPE[tok]
        elif tok in _REST:
            kind, value = "rest", "default"
        elif tok in _PRONOUN:
            kind, value = "pronoun", tok
        if kind is None:
            continue
        ms.append(Mention(kind, value, i, neg_pending))
        if kind in ("color", "bin", "shape"):
            neg_pending = False
    return ms


def _subjects(ms):
    """Subject keys of a unit, in order: (colour, shape) when a shape directly follows a colour, else colour,
    shape, or "default". Negated subjects ('all but red', 'not the red ones') are returned separately."""
    keys, negs = [], []
    used = set()
    for j, m in enumerate(ms):
        if j in used:
            continue
        if m.kind == "color":
            key = m.value
            if j + 1 < len(ms) and ms[j + 1].kind == "shape" and ms[j + 1].pos - m.pos <= 2:
                key = (m.value, ms[j + 1].value)
                used.add(j + 1)
            (negs if m.negated else keys).append((m.pos, key))
        elif m.kind == "shape":
            (negs if m.negated else keys).append((m.pos, m.value))
    has_color_or_shape = bool(keys or negs)
    if not has_color_or_shape and any(m.kind == "rest" for m in ms):
        keys.append((min(m.pos for m in ms if m.kind == "rest"), "default"))
    return keys, negs


def parse_instruction(text: str, task: str | None = None) -> ParseResult:
    if task == "sort_fixed":
        return ParseResult(dict(FIXED_MAPPING), "explicit", ["task sort_fixed: fixed mapping"])
    text = text or ""
    tokens = _tokens(text)
    words = set(tokens)
    raw = [_mentions(u) for u in _units(tokens)]
    raw = [ms for ms in raw if ms]

    # ---- merge units into (subjects, bins) statements
    statements = []      # (subjects [(pos,key)], negated subjects, bins [Mention])
    last_subjects = None
    i = 0
    while i < len(raw):
        ms = raw[i]
        subs, negsubs = _subjects(ms)
        bins = [m for m in ms if m.kind == "bin"]
        nxt = raw[i + 1] if i + 1 < len(raw) else None
        if subs and not bins and nxt is not None:
            nsubs, _ = _subjects(nxt)
            nbins = [m for m in nxt if m.kind == "bin"]
            if nbins and not nsubs:                   # "Red ones, put them in the left bin"
                statements.append((subs, negsubs, nbins))
                last_subjects = subs
                i += 2
                continue
            if len(nbins) == 1 and nsubs:              # "red and blue go left": share the bin
                statements.append((subs, negsubs, nbins))
                i += 1
                continue
        if bins and not subs:
            if nxt is not None:
                nsubs, nnegs = _subjects(nxt)
                nbins = [m for m in nxt if m.kind == "bin"]
                if nsubs and not nbins:                # "Left: red"
                    statements.append((nsubs, nnegs, bins))
                    last_subjects = nsubs
                    i += 2
                    continue
            if last_subjects:                          # "..., it goes right"
                statements.append((last_subjects, [], bins))
                i += 1
                continue
        if subs or bins:
            statements.append((subs, negsubs, bins))
            if subs:
                last_subjects = subs
        i += 1

    mapping, excl, notes = {}, {}, []

    def assign(key, b, why):
        if key in mapping and mapping[key] != b:
            notes.append(f"conflict for {key}: {mapping[key]} -> {b} ({why})")
        mapping[key] = b

    for subs, negsubs, bins in statements:
        if not subs or not bins:
            continue
        pos_bins = [b for b in bins if not b.negated]
        neg_bins = [b for b in bins if b.negated]
        for b in neg_bins:
            for _, k in subs:
                excl.setdefault(k, set()).add(b.value)
        if len(pos_bins) == 1:
            for _, k in subs:
                assign(k, pos_bins[0].value, "one bin")
        elif len(pos_bins) > 1 and len(pos_bins) == len(subs):
            for (_, k), b in zip(subs, pos_bins):
                assign(k, b.value, "paired in order")
        elif len(pos_bins) > 1 and len(subs) == 1:
            notes.append(f"several bins for {subs[0][1]}: {[b.value for b in pos_bins]}; took the last")
            assign(subs[0][1], pos_bins[-1].value, "last bin")
        elif pos_bins:
            # unequal counts: pair each subject with the nearest bin mention after it (else before it)
            for p, k in subs:
                after = [b for b in pos_bins if b.pos > p]
                b = after[0] if after else min(pos_bins, key=lambda b: abs(b.pos - p))
                assign(k, b.value, "nearest bin")
        # 'everything but red goes left': the negated subjects are excluded from that bin
        for _, k in negsubs:
            for b in pos_bins:
                excl.setdefault(k, set()).add(b.value)

    explicit = bool(mapping)

    # ---- global modifiers (only fill what is not explicit)
    base = None
    if words & _FIXED:
        base = dict(FIXED_MAPPING)
        notes.append("modifier: usual/default mapping")
    if words & _REVERSE:
        base = {"red": "right", "yellow": "center", "blue": "left"}
        notes.append("modifier: reversed mapping")
    if words & _SWAP:
        base = dict(base or FIXED_MAPPING)
        cs = [c for c in COLORS if c in words or c + "s" in words]
        bs = [b for b in BINS if any(_BIN.get(w) == b for w in words)]
        if len(cs) == 2:
            a, b = cs
            base[a], base[b] = base[b], base[a]
            notes.append(f"modifier: swap {a} and {b}")
            # the swap sentence names colours but no bins: those are not explicit assignments
            for c in cs:
                if c in mapping and not any(c == k for st in statements for _, k in st[0] if st[2]):
                    mapping.pop(c)
        elif len(bs) == 2:
            inv = {v: k for k, v in base.items()}
            a, b = bs
            base[inv[a]], base[inv[b]] = b, a
            notes.append(f"modifier: swap the {a} and {b} bins")
            mapping = {}  # "swap the left and right bins" names bins, not assignments
            explicit = False
    if base:
        for c, b in base.items():
            if c not in mapping and not (excl.get(c) and b in excl[c]):
                mapping[c] = b
        if not explicit:
            return ParseResult(mapping, "explicit", notes, excl)

    # ---- completion: one-to-one colour -> bin
    inferred = False
    if mapping or excl:
        for _ in range(3):
            changed = False
            colour_bins = {c: mapping[c] for c in COLORS if c in mapping}
            used = set(colour_bins.values())
            if len(used) != len(colour_bins):
                break                                   # not one-to-one: don't guess
            free_c = [c for c in COLORS if c not in mapping]
            free_b = [b for b in BINS if b not in used]
            if "default" in mapping:
                break                                   # "everything else" already covers the rest
            for c in free_c:
                allowed = [b for b in free_b if b not in excl.get(c, set())]
                if len(allowed) == 1 and (len(free_c) == 1 or excl.get(c)):
                    mapping[c] = allowed[0]
                    notes.append(f"inferred {c} -> {allowed[0]} (one-to-one)")
                    inferred = changed = True
                    break
            if not changed:
                break

    if not mapping:
        notes.append("nothing understood: fixed mapping")
        return ParseResult(dict(FIXED_MAPPING), "fallback", notes, excl)
    return ParseResult(mapping, "inferred" if inferred else "explicit", notes, excl)
