"""Structured records -> human-readable context blocks + source citations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Source:
    provider: str
    title: str
    url: str

    def to_dict(self) -> dict:
        return {"provider": self.provider, "title": self.title, "url": self.url}


def _lines(record: dict) -> list[str]:
    lines = [f"- title: {record.get('title') or 'unknown'} ({record.get('kind')})"]
    if record.get("year"):
        lines.append(f"- year: {record['year']}")
    if record.get("score") is not None:
        lines.append(f"- score: {record['score']:.1f}/10")
    if record.get("episodes") is not None:
        lines.append(f"- episodes: {record['episodes']}")
    if record.get("seasons") is not None:
        lines.append(f"- seasons: {record['seasons']}")
    if record.get("status"):
        lines.append(f"- status: {record['status']}")
    if record.get("genres"):
        lines.append(f"- genres: {', '.join(record['genres'])}")
    if record.get("director"):
        lines.append(f"- director: {record['director']}")
    if record.get("cast"):
        lines.append(f"- cast: {', '.join(record['cast'][:4])}")
    if record.get("reason"):
        lines.append(f"- why: {record['reason']}")
    return lines


def build_context(records: list[dict]) -> str:
    """Serialize records into the context block handed to the LLM."""
    blocks = []
    for i, record in enumerate(records, start=1):
        block = [f"[{i}] {record.get('title') or 'unknown'}"]
        block.extend(_lines(record))
        if record.get("overview"):
            overview = record["overview"]
            if len(overview) > 420:
                overview = overview[:420].rsplit(" ", 1)[0] + "…"
            block.append(f"- synopsis: {overview}")
        if record.get("url"):
            block.append(f"- source: {record['url']}")
        blocks.append("\n".join(block))
    return "\n\n".join(blocks)


def collect_sources(records: list[dict]) -> list[Source]:
    out, seen = [], set()
    for record in records:
        url = record.get("url") or ""
        key = (record.get("provider"), record.get("title"))
        if key in seen or not url:
            continue
        seen.add(key)
        out.append(Source(provider=record.get("provider") or "unknown", title=record.get("title") or "", url=url))
    return out