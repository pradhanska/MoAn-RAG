"""Entity extraction — turn a raw question into a structured query.

  "how many episodes does attack on titan have"  ->  Query(media="auto", title="attack on titan", intent="fact")
  "recommend an anime like Death Note"           ->  Query(media="anime", title="Death Note", intent="recommend")
"""

from __future__ import annotations

import re
from dataclasses import dataclass

ANIME_HINTS = ("anime", "manga", "manhwa", "waifu", "otaku", "sensei", "sakura")
TV_HINTS = ("tv show", "series", "television", "tv", "sitcom")
MOVIE_HINTS = ("movie", "film", "cinema", "directed", "director", "actor", "actress", "flick")

CRUFT_TRAILING = (
    "have", "has", "had", "about", "released", "release", "episodes", "episode count",
    "rating", "score", "rank", "like", "similar", "me", "in", "on", "at", "of", "with", "and",
    "the", "movie", "film",
)

LEADING = (
    r"tell\s+me\s+(?:about|everything\s+about|what\s+you\s+know\s+about)",
    r"what\s+(?:is|are|was|were)",
    r"who\s+(?:is|was|directed|directed\s+the)",
    r"when\s+(?:is|was|did)",
    r"where\s+(?:is|was)",
    r"which\s+",
    r"how\s+(?:many|much|long|good)",
    r"do\s+you\s+know",
    r"can\s+you\s+",
    r"is\s+there",
    r"are\s+there",
    r"recommend\s+(?:me\s+)?",
)

TITLE_PATTERNS = [
    re.compile(r'["\u201c\u201d\u2033](?P<t>[^"\u201c\u201d\u2033]+)["\u201c\u201d\u2033]'),
    re.compile(r"\bwho\s+directed\s+(?P<t>.+?)\s*\??$", re.I),
    re.compile(r"\bdirected\s+by\s+(?P<t>.+?)\s*\??$", re.I),
    re.compile(r"\bhow\s+many\s+(?:episodes|seasons)\s+(?:does\s+|did\s+)?(?P<t>.+?)\s*(?:have|has|had)?\s*\??$", re.I),
    re.compile(r"\b(?:when|what\s+year)\s+(?:was|is)\s+(?P<t>.+?)\s+(?:released|made)?\s*\??$", re.I),
    re.compile(r"\brelease\s+year\s+of\s+(?P<t>.+)", re.I),
    re.compile(r"\bif\s+(?:i|you)\s+liked\s+(?P<t>.+)", re.I),
    re.compile(r"\bsimilar\s+to\s+(?P<t>.+)", re.I),
    re.compile(r"\brecommend\s+(?:me\s+)?(?:an\s+|a\s+)?(?:anime|manga|movie|film|tv\s*show|series|show)\s+like\s+(?P<t>.+)", re.I),
    re.compile(r"\brecommend\s+(?:me\s+)?(?:an\s+|a\s+)?(?P<t>.+)", re.I),
    re.compile(r"\bwhat\s+is\s+(?P<t>.+?)\s+(?:about|based\s+on)\s*\??$", re.I),
]

QUOTE_RE = re.compile(r'["\u201c\u201d\u2033](?P<t>[^"\u201c\u201d\u2033]+)["\u201c\u201d\u2033]')


@dataclass
class Query:
    """A parsed question, ready for the retrieval layer."""

    media: str = "auto"          # auto | movie | tv | anime
    title: str | None = None
    intent: str = "fact"         # fact | recommend
    raw: str = ""                # the original question, verbatim

    def __bool__(self) -> bool:
        return bool(self.title)


def _clean(s: str) -> str:
    s = s.replace("?", "").strip()
    while True:
        hit = False
        for pat in LEADING:
            m = re.match(r"^\s*" + pat + r"\s+", s, flags=re.I)
            if m:
                s = s[m.end():]
                hit = True
                break
        if not hit:
            break
    # drop a leading "the" and any stray media word left over from the question
    s = re.sub(r"^the\s+", "", s, flags=re.I).strip()
    m = re.match(r"^(movie|film|anime|manga|tv show|tv series|tv|show|series|cinema)\s+(.+)$", s, flags=re.I)
    if m:
        s = re.sub(r"^the\s+", "", m.group(2).strip(), flags=re.I).strip()
    lower = s.strip().lower()
    while True:
        changed = False
        for word in CRUFT_TRAILING:
            if lower.endswith(" " + word):
                s = s[: -len(word) - 1].rstrip()
                lower = s.lower()
                changed = True
                break
        if not changed:
            break
    return s.strip()


def detect_media(question: str) -> str:
    lower = question.lower()
    if any(h in lower for h in ANIME_HINTS):
        return "anime"
    if any(h in lower for h in TV_HINTS):
        return "tv"
    if any(h in lower for h in MOVIE_HINTS):
        return "movie"
    return "auto"


def parse(question: str) -> Query:
    """Parse a raw question into a Query."""
    question = (question or "").strip()
    media = detect_media(question)

    intent = "recommend" if re.search(
        r"\b(recommend|similar|if\s+(?:i|you)\s+liked)\b", question, flags=re.I
    ) else "fact"

    title: str | None = None
    for pat in TITLE_PATTERNS:
        m = pat.search(question)
        if m and m.group("t").strip():
            title = m.group("t").strip().rstrip("?")
            break
    if not title:
        quoted = QUOTE_RE.search(question)
        if quoted:
            title = quoted.group("t").strip()
    if not title:
        title = _clean(question)

    return Query(media=media, title=title or None, intent=intent, raw=question)