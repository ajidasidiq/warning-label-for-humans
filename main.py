#!/usr/bin/env python3
"""Warning label for humans: pick the funniest one-line safety label.

The bounty asks for ONE line of comedy, at most 160 characters: the safety
warning label that should come printed on every human being. Funny first,
plausible second. The judge weighs, in order: the on-subject gate, the laugh
(the turn arriving in the last few words), recognition, label wording, and
fit inside 160 characters.

This program scores a shortlist of candidate lines against those five
criteria with deterministic, explainable rules, and writes the winner to
/output/entry.txt, the path the grader reads. Standard library only, no
network, no files outside this repository, deterministic on every run.
"""

import os
import re
import sys

# Candidate lines, written for this entry. Every one is a single line, a
# warning label for human beings, and 160 characters or fewer.
CANDIDATES = [
    "WARNING: This unit has no off switch, no user manual, and a 100% "
    "chance of saying 'I'm fine' when it is not.",
    "CAUTION: Contents under pressure. Do not shake, do not feed after "
    "midnight, and never ask how much sleep this unit got.",
    "WARNING: This human may suddenly take up a new hobby, buy all the "
    "equipment, and quit by Tuesday. Keep away from craft stores.",
    "CAUTION: This human will read the instructions, ignore the "
    "instructions, and blame the instructions, in that order.",
    "WARNING: This unit runs on eight hours of sleep it will never get. "
    "Do not operate heavy machinery or group chats before coffee.",
    "CAUTION: Prone to sudden dancing, crying at dog videos, and replying "
    "'haha' to messages it never read.",
    "WARNING: Contains one (1) human. May leak feelings at inappropriate "
    "times. Do not shake. Do not stack. Do not leave in sunlight.",
    "WARNING: This human's battery is not included, not replaceable, and "
    "somehow always at 3%. Charge with snacks and compliments.",
    "CAUTION: May spontaneously say 'just one more episode' at 2 a.m. "
    "and wake up a different person.",
    "WARNING: Do not tap the glass. The human inside is already anxious, "
    "already tired, and already pretending it read the terms.",
]

MAX_CHARS = 160

# Lexicons for the deterministic scorer. Each family is one recognizable
# piece of how humans actually behave; a line scores for the distinct
# families it touches, so piling on one joke does not inflate the score.
RECOGNITION_FAMILIES = [
    ["i'm fine", "i am fine", "i'm ok", "i'm okay"],
    ["sleep", "tired", "awake", "2 a.m.", "2am"],
    ["coffee", "caffeine"],
    ["off switch", "user manual", "manual", "instructions"],
    ["phone", "group chat", "message", "reply"],
    ["episode", "one more"],
    ["hobby", "craft", "equipment"],
    ["dog video", "dancing", "crying"],
    ["snack", "compliment", "charge"],
    ["battery", "3%"],
    ["anxious", "feelings", "leak"],
    ["terms", "read the terms", "pretend"],
    ["midnight", "tuesday", "sunlight"],
    ["shake", "stack"],
]

LABEL_WORDS = [
    "warning", "caution", "do not", "keep away", "contents",
    "unit", "contains", "may", "prone", "runs on", "battery",
    "not included", "not replaceable", "under pressure",
]

# Words that carry the punch: a contrast, a denial, or a confession. The
# laugh lands when one of these sits in the last few words of the line.
PUNCH_WORDS = [
    "not", "never", "no", "always", "somehow", "already", "pretend",
    "pretending", "blame", "quit", "different", "fine", "warning",
    "midnight", "tuesday", "sunlight", "3%",
]


def word_ngrams(text, n):
    words = re.findall(r"[a-z0-9%']+", text.lower())
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def repeated_phrase_penalty(text):
    """0.0 when nothing repeats, up to 1.0 for a heavily repeated line."""
    for n in (4, 3):
        grams = re.findall(r"[a-z0-9%']+", text.lower())
        seen = set()
        repeats = 0
        for i in range(len(grams) - n + 1):
            g = " ".join(grams[i:i + n])
            if g in seen:
                repeats += 1
            seen.add(g)
        if repeats:
            return min(1.0, 0.5 * repeats)
    return 0.0


def sentence_count(text):
    return max(1, text.count(".") + text.count("!") + text.count("?"))


def score(text):
    """Score one candidate against the judge's five criteria, in order.

    Returns (total, breakdown dict). The on-subject gate is a multiplier:
    a line that is not a warning label for humans scores zero outright.
    """
    n = len(text)
    lower = text.lower()
    words = re.findall(r"[a-z0-9%']+", lower)

    # 1. On-subject gate: label opener + a human subject.
    opener = lower.startswith("warning:") or lower.startswith("caution:")
    subject = any(w in lower for w in ("human", "unit", "contents", "person"))
    if not (opener and subject):
        return 0.0, {"gate": 0.0, "turn": 0.0, "recognition": 0.0,
                     "label": 0.0, "length": 0.0, "repeat_penalty": 0.0,
                     "chars": n}
    if n == 0 or n > MAX_CHARS or not text.strip():
        return 0.0, {"gate": 0.0, "turn": 0.0, "recognition": 0.0,
                     "label": 0.0, "length": 0.0, "repeat_penalty": 0.0,
                     "chars": n}

    # 2. The laugh: the turn arrives in the last few words. Find the last
    # punch word and reward it for sitting close to the end of the line.
    tail = lower[-40:]
    punch_ends = [m.end() for m in re.finditer(r"[a-z0-9%']+", tail)
                  if m.group(0) in PUNCH_WORDS]
    if punch_ends:
        turn = 1.0 - (len(tail) - max(punch_ends)) / 40.0
    else:
        turn = 0.2
    # A quoted line of speech is a turn by itself ("I'm fine").
    if "'" in text and any(q in lower for q in ("i'm fine", "haha",
                                                "just one more episode")):
        turn = min(1.0, turn + 0.15)

    # 3. Recognition: distinct universal-behavior families touched.
    families = sum(1 for fam in RECOGNITION_FAMILIES
                   if any(alt in lower for alt in fam))
    recognition = min(1.0, families / 4.0)

    # 4. Label wording: how much it sounds like a real printed label.
    label_hits = sum(1 for w in LABEL_WORDS if w in lower)
    label = min(1.0, label_hits / 5.0)

    # 5. Fit: use the whole line, no filler. Best between 100 and 160 chars.
    if n >= 100:
        length = 1.0
    else:
        length = max(0.0, n / 100.0)

    # Penalties: a repeated joke, and a second idea bolted on.
    repeat = repeated_phrase_penalty(text)
    extra_ideas = max(0, sentence_count(text) - 2) * 0.10

    total = (0.30 * turn + 0.25 * recognition + 0.20 * label
             + 0.15 * length - 0.15 * repeat - extra_ideas)
    breakdown = {
        "gate": 1.0, "turn": round(turn, 3),
        "recognition": round(recognition, 3), "label": round(label, 3),
        "length": round(length, 3), "repeat_penalty": round(repeat, 3),
        "chars": n,
    }
    return total, breakdown


def pick(candidates):
    ranked = sorted(((score(t)[0], score(t)[1], t) for t in candidates),
                    key=lambda row: (-row[0], len(row[2])))
    return ranked


def main():
    ranked = pick(CANDIDATES)
    best_score, best_breakdown, best = ranked[0]
    for rank, (total, breakdown, text) in enumerate(ranked, 1):
        print(f"{rank:2d}. {total:6.3f}  ({breakdown['chars']:3d} chars)  {text}")
    print()
    print(f"WINNER ({best_breakdown['chars']} chars, score {best_score:.3f}):")
    print(best)

    out_path = os.environ.get("ENTRY_OUTPUT", "/output/entry.txt")
    written = None
    last_error = None
    for candidate_path in (out_path, "output/entry.txt", "entry.txt"):
        try:
            parent = os.path.dirname(candidate_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(candidate_path, "w", encoding="utf-8") as fh:
                fh.write(best)
            written = candidate_path
            break
        except OSError as exc:  # pragma: no cover - sandbox path differs
            last_error = exc
    if written is None:
        print(f"ERROR: could not write entry: {last_error}", file=sys.stderr)
        return 1
    print(f"Wrote {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
