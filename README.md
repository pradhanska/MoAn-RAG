# CineAI — Movie & Anime Q&A

A conversational AI that answers questions about **movies, TV shows, anime, and manga** — grounded in real, verifiable data instead of LLM guesswork.

> Ask things like *"Who directed Spirited Away?"*, *"How many episodes does Attack on Titan have?"*, or *"Recommend an anime like Death Note"* and get an answer backed by an actual source link.

Demo landing page: [moan-rag.pages.dev](https://moan-rag.pages.dev/) — the chat app runs with `streamlit run app.py`.

---

## Why This Project?

Most LLMs answer from memory, which means they can **hallucinate facts**, go stale after their training cutoff, and give you no way to verify what they said.

CineAI follows one simple rule: **look it up first, then let the AI phrase the answer.** Every fact returned (director, episode count, rating, release year, recommendations) is pulled live from a public database and can be independently verified on IMDb, TMDB.org, MyAnimeList.net or TVMaze — with the source link printed right next to the answer.

## How It Works (RAG Pipeline)

```
User Question
      │
      ▼
Entity Extraction → title + media type + intent
      │
      ▼
Retrieval → Jikan · TVMaze · TMDB · OMDb (live APIs)
      │
      ▼
Context Block → structured facts + source URLs
      │
      ▼
Generation → grounded LLM answer  (or local template, zero keys)
      │
      ▼
Answer + Citations → chat UI / CLI
```

1. **You ask a question** — *"how many episodes does attack on titan have"*
2. **Entity extraction** picks the title, the media type (anime / TV / movie), and the intent (fact / recommendation).
3. **The right sources are queried**: Jikan & TVMaze need **no API keys**; TMDB & OMDb activate automatically when you add keys.
4. **Retrieved facts are formatted into a context block** (rating, status, episodes, genres, synopsis, link).
5. **A grounded answer is generated** — strictly from that context. Without an LLM key, a local template assembles the answer from the same facts, so the app is fully usable out of the box.
6. **Sources are cited** beside every answer. Nothing is invented.

## Project Layout

```
moan-rag/
├── app.py                 # Streamlit chat UI (the fun part)
├── cli.py                 # Terminal demo — no UI needed
├── moan/                  # core package
│   ├── extract.py         # question → title / media / intent
│   ├── apis.py            # Jikan · TVMaze · TMDB · OMDb wrappers
│   ├── context.py         # records → context block + source citations
│   ├── generate.py        # grounded LLM call + zero-key template answer
│   └── pipeline.py        # parse → retrieve → context → generate
├── tests/test_pipeline.py # offline tests (no network, no keys)
├── index.html             # CineAI landing page (deployed at /)
├── requirements.txt
└── .env.example           # optional keys (TMDB / OMDb / LLM)
```

## Getting Started

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# try it in the terminal right away (no keys needed)
python cli.py "how many episodes does Attack on Titan have"
python cli.py "recommend an anime like Death Note"

# or open the chat UI
streamlit run app.py
```

It works instantly with **zero API keys** — anime and TV data come from Jikan and TVMaze, and answers are generated locally from the retrieved facts.

## Data Sources

| Source | Covers | Key needed? |
| --- | --- | --- |
| [Jikan](https://jikan.moe/) (MyAnimeList) | Anime · manga · recommendations · directors | ❌ free |
| [TVMaze](https://www.tvmaze.com/api) | TV shows · seasons · episodes | ❌ free |
| [TMDB](https://www.themoviedb.org/settings/api) | Movies · TV (full profiles) | ✅ `TMDB_API_KEY` |
| [OMDb](https://www.omdbapi.com/apikey.aspx) | Movies (director · cast · IMDb rating) | ✅ `OMDB_API_KEY` |

Copy `.env.example` to `.env` and add keys to unlock movie-grade answers:

```bash
cp .env.example .env   # then fill in TMDB_API_KEY / OMDB_API_KEY
```

## LLM (optional)

Any **OpenAI-compatible** endpoint works — no SDK required:

```bash
# Groq (fast, free tier)
LLM_API_KEY=…            LLM_BASE_URL=https://api.groq.com/openai/v1

# Local Ollama
LLM_BASE_URL=http://localhost:11434/v1
```

Without a key, answers come from the built-in grounded template engine. Either way the answer is built **only from the retrieved context** — the LLM is a phrasing layer, never the source of truth.

## Tests

Offline unit tests — no network, no keys:

```bash
python -m tests.test_pipeline     # or: pytest
```

## Sample Questions

```
who directed Spirited Away?                  → TMDB/OMDb + Jikan
how many episodes does Attack on Titan have? → Jikan / TVMaze
how many seasons does Breaking Bad have?     → TVMaze
recommend an anime like Death Note           → MyAnimeList recommendations
what is One Piece about?                     → Jikan / TVMaze
```

## Roadmap

- [x] Keyless anime + TV retrieval (Jikan, TVMaze)
- [x] Local grounded answer engine (zero keys)
- [x] Optional OpenAI-compatible LLM layer
- [x] Streamlit chat UI + terminal CLI + tests
- [ ] Movie search UX without keys (embedded lightweight dataset)
- [ ] Chat memory & follow-up questions
- [ ] One-click deploy to Cloudflare Pages

## License

MIT — build on it, remix it, ship it.