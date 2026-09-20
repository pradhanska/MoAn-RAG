"""The RAG pipeline — question in, grounded answer out.

  parse() → retrieve() → build_context() → generate()
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import apis, context, extract
from .extract import Query
from .generate import LLMClient, template_answer

MODE_AUTO = "auto"
MODE_LLM = "llm"
MODE_TEMPLATE = "template"


@dataclass
class Answer:
    question: str
    answer: str
    provider: str = "local_template"   # "llm·<model>" or "local_template"
    model: str | None = None
    sources: list[context.Source] = field(default_factory=list)
    context: str = ""
    warnings: list[str] = field(default_factory=list)
    query: Query = field(default_factory=Query)

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "answer": self.answer,
            "provider": self.provider,
            "model": self.model,
            "sources": [s.to_dict() for s in self.sources],
            "context": self.context,
            "warnings": self.warnings,
            "query": {"media": self.query.media, "title": self.query.title, "intent": self.query.intent},
        }


def retrieve(query: Query) -> tuple[list[dict], list[str]]:
    """Fetch records for a parsed query. Returns (records, warnings)."""
    if not query.title:
        return [], ["I couldn't work out which title you meant — try quoting it, e.g. \"Spirited Away\"."]

    want_episodes = "episodes" in query.raw.lower() or "seasons" in query.raw.lower()
    order = apis.search_order(query.media, want_episodes=want_episodes)
    records: list[dict] = []
    warnings: list[str] = []

    for fn, label in order:
        if label == "tmdb" and not _has_key("TMDB_API_KEY"):
            continue
        if label == "omdb" and not _has_key("OMDB_API_KEY"):
            continue
        try:
            batch = fn(query.title) or []
        except Exception:
            batch = []
        if batch:
            records = batch
            break

    # one lazy enrichment call only when the question actually asks for a director
    if records and "director" in query.raw.lower():
        top = records[0]
        if top.get("provider") == "jikan" and top.get("mal_id") and not top.get("director"):
            try:
                top["director"] = apis.jikan_director(top.get("mal_id"))
            except Exception:
                pass

    # recommendations — MyAnimeList via Jikan (honest “not available” when MAL is down)
    if records and query.intent == "recommend":
        top = records[0]
        if top.get("provider") == "jikan" and top.get("mal_id"):
            try:
                extra = apis.jikan_recommendations(top.get("mal_id"), limit=4)
            except Exception:
                extra = []
            if extra:
                records = [top] + extra

    if not records:
        hints = []
        for fn, label in order:
            if label in ("tmdb", "omdb"):
                continue
            try:
                hints.extend((fn(query.title) or [])[:1])
            except Exception:
                pass
        names = [f"\"{r.get('title')}\"" for r in hints[:2] if r.get("title")]
        msg = f"I couldn't find \"{query.title}\" in the movie/anime databases."
        if names:
            msg += f" Closest match: {', '.join(names)}."
        msg += " Double-check the spelling — or add TMDB/OMDb keys for fuller movie/TV coverage."
        warnings.append(msg)
        if query.media == "movie" and not (_has_key("TMDB_API_KEY") or _has_key("OMDB_API_KEY")):
            warnings.append(
                "Heads-up: no TMDB/OMDb keys are set, so film coverage is limited right now. "
                "Add them to .env and movies (directors, cast, ratings) unlock."
            )
    return records, warnings


def _has_key(name: str) -> bool:
    import os
    return bool(os.getenv(name, "").strip())


def ask(question: str, mode: str = MODE_AUTO) -> Answer:
    """Run the full pipeline on one question."""
    query = extract.parse(question)
    records, warnings = retrieve(query)
    context_text = context.build_context(records)
    sources = context.collect_sources(records)

    provider = "local_template"
    model = None

    if not records:
        answer_text = warnings[0] if warnings else "No data was retrieved for that question."
    elif mode == MODE_TEMPLATE:
        answer_text = template_answer(records, question, intent=query.intent)
    else:
        client = LLMClient.from_env()
        if client is None and mode == MODE_LLM:
            warnings.append("LLM requested but LLM_API_KEY / LLM_BASE_URL are not set — used the local template generator instead.")
        if client:
            generated = client.generate(context_text, question)
            if generated:
                answer_text = generated
                provider, model = f"llm·{client.model}", client.model
            else:
                answer_text = template_answer(records, question, intent=query.intent)
                provider = "template (llm call failed)"
        else:
            answer_text = template_answer(records, question, intent=query.intent)

    return Answer(
        question=question,
        answer=answer_text,
        provider=provider,
        model=model,
        sources=sources,
        context=context_text,
        warnings=warnings,
        query=query,
    )