"""Data-source wrappers — Jikan (anime/manga), TVMaze (TV), TMDB & OMDb (movies).

Every provider normalises results into a shared record shape:

    {
      "provider": str,        # "jikan" | "tvmaze" | "tmdb" | "omdb"
      "kind":     str,        # "anime" | "manga" | "tv" | "movie"
      "title":    str,
      "year":     str | None,
      "url":      str,
      "score":    float | None,
      "episodes": int | None,
      "status":   str | None,
      "genres":   list[str],
      "overview": str | None,
      "director": str | None,
      "cast":     list[str],
    }

Jikan and TVMaze are keyless — the app works out of the box for anime/tv.
TMDB and OMDb activate automatically when `TMDB_API_KEY` / `OMDB_API_KEY` are set.
"""

from __future__ import annotations

import os

import time

try:
    import requests
except ImportError:  # pragma: no cover - requirements always include requests
    requests = None  # type: ignore[assignment]

TIMEOUT = 14
JIKAN = "https://api.jikan.moe/v4"
TVMAZE = "https://api.tvmaze.com"

_EMPTY: tuple = ()


def _get(url: str, params: dict | None = None, timeout: int = TIMEOUT) -> dict | list | None:
    if requests is None:
        return None
    for attempt in range(2):  # one lightweight retry for transient 429/timeouts
        try:
            resp = requests.get(url, params=params or {}, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            if attempt == 0:
                time.sleep(0.8)
                continue
    return None


def _num(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- Jikan
def jikan_search(query: str, limit: int = 3) -> list[dict]:
    """Search anime + manga on MyAnimeList via Jikan (keyless)."""
    data = _get(f"{JIKAN}/anime", {"q": query, "limit": limit, "order_by": "popularity", "sort": "asc"})
    out: list[dict] = []
    for item in (data or {}).get("data", [])[:limit]:
        genres = [g["name"] for g in item.get("genres", [])]
        out.append({
            "provider": "jikan",
            "kind": "anime",
            "title": item.get("title") or item.get("title_english") or "",
            "year": (item.get("aired") or {}).get("prop", {}).get("from", {}).get("year"),
            "url": item.get("url", ""),
            "mal_id": item.get("mal_id"),
            "score": _num(item.get("score")),
            "episodes": item.get("episodes"),
            "status": item.get("status"),
            "genres": genres,
            "overview": item.get("synopsis"),
            "director": None,
            "cast": [],
        })
    return out


def jikan_director(mal_id: int | None) -> str | None:
    """Director for an anime (lazy — one extra request, only when asked)."""
    if not mal_id:
        return None
    data = _get(f"{JIKAN}/anime/{mal_id}/full")
    staff = data or {}
    for person in staff.get("data", {}).get("staff", []):
        if any(p.get("position") == "Director" for p in person.get("positions", [])):
            return person.get("person", {}).get("name")
    return None


def jikan_recommendations(mal_id: int | None, limit: int = 4) -> list[dict]:
    """Anime recommendations for a title (from MyAnimeList)."""
    if not mal_id:
        return []
    data = _get(f"{JIKAN}/anime/{mal_id}/recommendations")
    out: list[dict] = []
    for item in (data or {}).get("data", [])[:limit]:
        entry = item.get("entry", {})
        out.append({
            "provider": "jikan",
            "kind": "anime",
            "title": entry.get("title", ""),
            "year": None,
            "url": entry.get("url", ""),
            "mal_id": entry.get("mal_id"),
            "score": None,
            "episodes": None,
            "status": None,
            "genres": [],
            "overview": None,
            "director": None,
            "cast": [],
            "reason": item.get("reason", ""),
        })
    return out


# ---------------------------------------------------------------- TVMaze
def tvmaze_search(query: str, want_episodes: bool = False) -> list[dict]:
    """Search TV shows on TVMaze (keyless). Episodes fetched when asked for."""
    data = _get(f"{TVMAZE}/singlesearch/shows", {"q": query})
    if not isinstance(data, dict):
        return []
    show = data
    episodes = None
    seasons = None
    if want_episodes:
        eps = _get(f"{TVMAZE}/shows/{show.get('id')}/episodes")
        if isinstance(eps, list):
            episodes = len(eps)
            seasons = len({e.get("season") for e in eps if e.get("season") is not None})
    genres = [g for g in show.get("genres", []) if isinstance(g, str)]
    return [{
        "provider": "tvmaze",
        "kind": "tv",
        "title": show.get("name", ""),
        "year": _year_from(show.get("premiered")),
        "url": show.get("url", ""),
        "score": _num(show.get("rating", {}).get("average")),
        "episodes": episodes,
        "seasons": seasons,
        "status": show.get("status"),
        "genres": genres,
        "overview": show.get("summary") and _strip_tags(show["summary"]),
        "director": None,
        "cast": [],
    }]


def _year_from(date_str: str | None) -> str | None:
    return str(date_str)[:4] if date_str else None


def _strip_tags(html: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", html).strip()


# ---------------------------------------------------------------- TMDB
def tmdb_search(query: str) -> list[dict]:
    """Search movies + TV on TMDB (requires TMDB_API_KEY)."""
    key = os.getenv("TMDB_API_KEY", "").strip()
    if not key:
        return []
    data = _get("https://api.themoviedb.org/3/search/multi", {"api_key": key, "query": query, "adult": "false"})
    out: list[dict] = []
    for item in (data or {}).get("results", [])[:3]:
        media = item.get("media_type", "movie")
        out.append({
            "provider": "tmdb",
            "kind": "movie" if media == "movie" else "tv",
            "title": item.get("title") or item.get("name") or "",
            "year": _year_from(item.get("release_date") or item.get("first_air_date")),
            "url": f"https://www.themoviedb.org/{media}/{item.get('id')}",
            "score": _num(item.get("vote_average")),
            "episodes": None,
            "status": None,
            "genres": [],
            "overview": item.get("overview"),
            "director": None,
            "cast": [],
        })
    return out


# ---------------------------------------------------------------- OMDb
def omdb_search(query: str) -> list[dict]:
    """Search movies on OMDb (requires OMDB_API_KEY)."""
    key = os.getenv("OMDB_API_KEY", "").strip()
    if not key:
        return []
    data = _get("https://www.omdbapi.com/", {"apikey": key, "t": query, "plot": "short"})
    if not isinstance(data, dict) or data.get("Response") != "True":
        return []
    kind = "movie" if data.get("Type") == "movie" else "tv"
    cast = [c.strip() for c in str(data.get("Actors", "")).split(",") if c.strip()][:4]
    return [{
        "provider": "omdb",
        "kind": kind,
        "title": data.get("Title", ""),
        "year": data.get("Year"),
        "url": f"https://www.imdb.com/title/{data.get('imdbID', '')}/",
        "score": _num(data.get("imdbRating")),
        "episodes": _int_or_none(data.get("totalSeasons")),
        "status": None,
        "genres": [g.strip() for g in str(data.get("Genre", "")).split(",") if g.strip()],
        "overview": data.get("Plot"),
        "director": data.get("Director"),
        "cast": cast,
    }]


def _int_or_none(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- routing
def search_order(media: str, want_episodes: bool = False) -> list[tuple]:
    """Order in which providers are tried for a given media hint.

    Returns list of (callable, label). The first provider to return results wins.
    """
    if media == "anime":
        return [
            (jikan_search, "jikan"),
            (lambda q: tvmaze_search(q, want_episodes), "tvmaze"),
            (tmdb_search, "tmdb"),
        ]
    if media == "tv":
        return [
            (lambda q: tvmaze_search(q, want_episodes), "tvmaze"),
            (tmdb_search, "tmdb"),
            (jikan_search, "jikan"),
        ]
    if media == "movie":
        return [
            (tmdb_search, "tmdb"),
            (omdb_search, "omdb"),
            (jikan_search, "jikan"),
            (lambda q: tvmaze_search(q, want_episodes), "tvmaze"),
        ]
    # auto — try everything, keyless sources first
    return [
        (lambda q: tvmaze_search(q, want_episodes), "tvmaze"),
        (jikan_search, "jikan"),
        (tmdb_search, "tmdb"),
        (omdb_search, "omdb"),
    ]