"""Answer generation — grounded LLM call with a zero-dependency template fallback.

The LLM is optional: `LLM_API_KEY` + `LLM_BASE_URL` activate any OpenAI-compatible
endpoint (Groq, OpenAI, OpenRouter, local Ollama at http://localhost:11434/v1, ...).
Without a key the app answers with `template_answer`, which assembles a natural
sentence purely from retrieved facts — every answer stays grounded either way.
"""

from __future__ import annotations

import os


SYSTEM_PROMPT = (
    "You are CineAI, a movie & anime assistant. Answer the user's question using ONLY "
    "the provided context. Never invent facts, ratings, dates or titles that are not in "
    "the context. If the context does not contain the answer, say so plainly and point "
    "to the sources. Cite sources inline like [1] / [provider]. Be friendly and concise."
)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


class LLMClient:
    """Minimal OpenAI-compatible chat client (requests only, no SDK)."""

    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    @classmethod
    def from_env(cls) -> "LLMClient | None":
        key = _env("LLM_API_KEY")
        base = _env("LLM_BASE_URL", "https://api.openai.com/v1")
        model = _env("LLM_MODEL", cls._default_model(base))
        if not key:
            return None
        return cls(key, base, model)

    @staticmethod
    def _default_model(base_url: str) -> str:
        b = base_url.lower()
        if "groq" in b:
            return "llama-3.3-70b-versatile"
        if "ollama" in b or "localhost" in b or "127.0.0.1" in b:
            return "llama3.2"
        if "openrouter" in b:
            return "meta-llama/llama-3.3-70b-instruct:free"
        return "gpt-4o-mini"

    def generate(self, context: str, question: str) -> str | None:
        try:
            import requests
        except ImportError:
            return None
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "max_tokens": 420,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION: {question}"},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            resp = requests.post(f"{self.base_url}/chat/completions", json=payload, headers=headers, timeout=40)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception:
            return None


# ---------------------------------------------------------------- template
def template_answer(records: list[dict], question: str, intent: str = "fact") -> str:
    """Zero-dependency answer from the retrieved records."""
    if not records:
        return "I couldn't find a match for that title in the movie/anime databases."

    top = records[0]
    name = top.get("title") or "that title"
    kind = top.get("kind") or "title"
    q = question.lower()
    sentences: list[str] = []

    # recommendations are a distinct answer shape — use extras as the payload
    if intent == "recommend":
        recs = [r for r in records[1:] if r.get("title")]
        if recs:
            bits = []
            for rec in recs[:4]:
                bit = f'"{rec["title"]}"'
                if rec.get("reason"):
                    reason = rec["reason"].strip()
                    if len(reason) > 110:
                        reason = reason[:110].rsplit(" ", 1)[0] + "…"
                    bit += f" — {reason}"
                bits.append(bit)
            return (
                f"If you liked {name}, you might enjoy: {'; '.join(bits)}. "
                "Each pick is a verified MyAnimeList recommendation — tap the sources for details."
            )
        return f"I found {name} but no verified recommendations were available for it."

    if "directed" in q or "director" in q:
        if top.get("director"):
            sentences.append(f"{name} was directed by {top['director']} ({kind}, {top.get('year') or 'year unknown'}).")
        else:
            sentences.append(f"I found {name} but the database does not list a director for it.")
    elif "episodes" in q or "season" in q:
        if "seasons" in q and top.get("seasons"):
            sentences.append(f"{name} has {top['seasons']} seasons ({kind}, {top.get('year') or 'year unknown'}).")
        elif top.get("episodes"):
            sentences.append(f"{name} has {top['episodes']} episodes ({kind}, {top.get('year') or 'year unknown'}).")
        else:
            sentences.append(f"{name} ({kind}) — I couldn't confirm an episode/season count from the source data.")
    elif "year" in q or "released" in q or "when" in q:
        sentences.append(f"{name} was released in {top.get('year') or 'an unknown year'} ({kind}).")
    elif "rating" in q or "score" in q or "good" in q or "rank" in q:
        if top.get("score") is not None:
            sentences.append(f"{name} has a rating of {top['score']:.1f}/10 ({kind}, {top.get('year') or 'year unknown'}).")
        else:
            sentences.append(f"No rating was available for {name} in the source data.")
    else:
        intro = f"{name} is a {kind}"
        if top.get("year"):
            intro += f" from {top['year']}"
        if top.get("genres"):
            intro += f" in the {', '.join(top['genres'][:3])} vein"
        intro += "."
        sentences.append(intro)

    if len(records) > 1 and not any("couldn't" in s or "could not" in s for s in sentences):
        alt = ", ".join(f"\"{r.get('title')}\"" for r in records[1:3] if r.get("title"))
        if alt:
            sentences.append(f"Other close matches: {alt}.")

    if top.get("overview"):
        overview = top["overview"]
        if len(overview) > 300:
            overview = overview[:300].rsplit(" ", 1)[0] + "…"
        sentences.append(f"Quick synopsis: {overview}")

    return " ".join(sentences)