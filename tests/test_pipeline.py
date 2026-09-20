"""Offline unit tests — no network, no API keys.

Run:  python -m tests.test_pipeline     (or: pytest)
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from moan import context, extract  # noqa: E402
from moan.generate import template_answer  # noqa: E402


# ---------------------------------------------------------------- extract
def test_extract_director():
    q = extract.parse("who directed Spirited Away")
    assert q.title and "spirited away" in q.title.lower()
    assert q.intent == "fact"


def test_extract_episodes():
    q = extract.parse("how many episodes does attack on titan have")
    assert q.title and "attack on titan" in q.title.lower()
    assert q.media in ("tv", "auto", "anime")


def test_extract_quoted():
    q = extract.parse('Tell me about "Cowboy Bebop"')
    assert q.title == "Cowboy Bebop"


def test_extract_recommend():
    q = extract.parse("recommend an anime like Death Note")
    assert q.intent == "recommend"
    assert q.title and "death note" in q.title.lower()


def test_extract_media_hint():
    assert extract.detect_media("is there a good manga like berserk") == "anime"
    assert extract.detect_media("who starred in the movie Inception") == "movie"


# ---------------------------------------------------------------- context
RECORD = {
    "provider": "jikan", "kind": "anime", "title": "Attack on Titan",
    "year": "2013", "url": "https://myanimelist.net/anime/16498",
    "score": 8.5, "episodes": 25, "status": "Finished",
    "genres": ["Action", "Drama"], "overview": "Humans fight giants.",
    "director": None, "cast": [],
}


def test_context_contains_facts():
    text = context.build_context([RECORD])
    assert "Attack on Titan" in text
    assert "episodes: 25" in text
    assert "https://myanimelist.net" in text


def test_sources_dedupe():
    sources = context.collect_sources([RECORD, RECORD])
    assert len(sources) == 1
    assert sources[0].provider == "jikan"


# ---------------------------------------------------------------- template
def test_template_episodes():
    out = template_answer([RECORD], "how many episodes does attack on titan have")
    assert "25" in out


def test_template_unknown_handled():
    out = template_answer([], "who directed something")
    assert "couldn't find" in out.lower()


def test_template_recommend():
    from moan.generate import template_answer as ta

    recs = [dict(RECORD), {**RECORD, "title": "Death Note", "reason": "similar mind games"}]
    out = ta(recs, "recommend an anime like attack on titan", intent="recommend")
    assert "Death Note" in out


# ---------------------------------------------------------------- apis (offline fixtures)
JIKAN_FIXTURE = {
    "data": [
        {
            "mal_id": 199,
            "title": "Spirited Away",
            "title_english": "Spirited Away",
            "aired": {"prop": {"from": {"year": 2001}}},
            "url": "https://myanimelist.net/anime/199/Spirited_Away",
            "score": 8.78,
            "episodes": 125,
            "status": "Finished Airing",
            "genres": [{"name": "Adventure"}, {"name": "Supernatural"}],
            "synopsis": "A young girl wanders into a world of spirits.",
        }
    ]
}


def test_jikan_search_parses_fixture():
    from unittest.mock import patch

    from moan import apis

    with patch.object(apis, "_get", return_value=JIKAN_FIXTURE):
        records = apis.jikan_search("spirited away")
    assert records and records[0]["title"] == "Spirited Away"
    assert records[0]["year"] == 2001
    assert records[0]["kind"] == "anime"
    assert records[0]["episodes"] == 125
    assert records[0]["genres"] == ["Adventure", "Supernatural"]


def test_jikan_search_zero_results_is_empty_list():
    from unittest.mock import patch

    from moan import apis

    with patch.object(apis, "_get", return_value={"data": []}):
        assert apis.jikan_search("zzz none") == []
    with patch.object(apis, "_get", return_value=None):
        assert apis.jikan_search("zzz none") == []


# ---------------------------------------------------------------- runner
def test_all() -> bool:
    tests = [(k, v) for k, v in sorted(globals().items())
             if k.startswith("test_") and k != "test_all" and callable(v)]
    failures = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ✔ {name}")
        except AssertionError as exc:
            failures += 1
            print(f"  ✘ {name}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return failures == 0


if __name__ == "__main__":
    ok = test_all()
    sys.exit(0 if ok else 1)