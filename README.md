# Movie & Anime Q&A AI

A conversational AI that answers questions about **movies, TV shows, anime, and manga** using free public APIs. Built on a **Retrieval-Augmented Generation (RAG)** pipeline, so every answer is grounded in real, verifiable data instead of LLM guesswork.

> Ask things like *"Who directed Spirited Away?"*, *"How many episodes does Attack on Titan have?"*, or *"What anime should I watch if I liked Death Note?"* and get an answer backed by an actual source.

Demo: [CLICK HERE](https://moan-rag.pages.dev/)
---

## Why This Project?

Most LLMs answer from memory, which means they can hallucinate facts, go stale after their training cutoff, and give you no way to check if they're right.

This project fixes that by following a simple rule: **look it up first, then let the AI just phrase the answer.** Every fact returned (director, episode count, rating, release year) is pulled live from a public database and can be independently verified on IMDb, TMDB.org, or MyAnimeList.net.

---

## How It Works (RAG Pipeline)

```
User Question
      │
      ▼
Identify Title / Media Type
      │
      ▼
Query the Right API (TMDB / OMDb / Jikan)
      │
      ▼
Structured Data Returned (JSON)
      │
      ▼
Format Data as Context
      │
      ▼
LLM Prompt: "Answer using ONLY this context"
      │
      ▼
Natural-Language Answer + Source Citation
      │
      ▼
Chat UI
```

1. **User asks a question** through the chat interface.
2. **Entity extraction** identifies the title and likely media type (movie, TV show, anime, manga).
3. **The right API is queried**:
   - Movies/TV → TMDB or OMDb
   - Anime/Manga → Jikan
4. **Structured data is formatted into context** (e.g. director, cast, release year, rating).
5. **The LLM receives the context + question** and is instructed to answer only from that data — preventing hallucination.
6. **A natural-language answer is generated**, with the source cited.
7. **The answer is returned to the chat UI.**

---

## Tech Stack

| Component | Tool / Service | Notes |
|---|---|---|
| LLM (answer generation) | Claude / Gemini / Groq (Llama 3) / Ollama | Free tiers or fully local |
| Movie/TV data | [TMDB API](https://www.themoviedb.org/documentation/api), [OMDb API](https://www.omdbapi.com/) | Free API keys required |
| Anime/Manga data | [Jikan API](https://jikan.moe/) | No API key needed |
| Frontend | Streamlit or Gradio | Free, fast to build |
| Hosting | Hugging Face Spaces / Streamlit Cloud | Free tier deployment |
| Optional vector store | Chroma / FAISS | Only needed for large local datasets |

---

## Project Scope

**In scope:**
- Lookup of movies, TV shows, anime, manga (cast, crew, plot, ratings, release dates, genres)
- Genre/mood-based recommendations
- Trivia-style Q&A
- Comparison queries between titles

**Out of scope:**
- Streaming/piracy links — metadata only, no content access
- Subjective "best ever" claims stated as fact
- Real-time box office or streaming-availability data

---

## Why This Topic Is Easy to Verify

- Every fact (release year, episode count, director, rating) is a single, objective data point — no interpretation needed.
- Anyone can cross-check the same title on IMDb, TMDB, or MyAnimeList in a browser.
- Unlike medical, legal, or financial topics, an incorrect answer here carries no real-world risk — making it a safe, demonstrable sandbox for learning RAG and LLM prompting.

---

## Getting Started

### 1. Prerequisites
- Python 3.9+
- Free API keys:
  - [TMDB API key](https://www.themoviedb.org/settings/api)
  - [OMDb API key](https://www.omdbapi.com/apikey.aspx)
- An LLM API key (Claude, Gemini, or Groq) — or [Ollama](https://ollama.com/) installed locally for a fully free, offline option

### 2. Installation
```bash
git clone <repo-url>
cd movie-anime-qa-ai
pip install -r requirements.txt
```

### 3. Environment variables
Create a `.env` file:
```
TMDB_API_KEY=your_tmdb_key
OMDB_API_KEY=your_omdb_key
LLM_API_KEY=your_llm_key
```

### 4. Run the app
```bash
streamlit run app.py
```

---

## Project Structure
```
movie-anime-qa-ai/
├── app.py              # Streamlit chat UI
├── apis/
│   ├── tmdb.py          # TMDB API wrapper
│   ├── omdb.py          # OMDb API wrapper
│   └── jikan.py         # Jikan (anime/manga) API wrapper
├── llm/
│   └── generate.py       # Prompt construction + LLM calls
├── requirements.txt
├── .env.example
└── README.md
```

---

## Evaluation / Testing

- **Accuracy testing**: Run a fixed set of test questions and manually confirm answers against the source API/site.
- **Recommendation testing**: Check that suggested titles genuinely share genre/theme with the reference title.
- **Edge case testing**: Confirm the system says *"I couldn't find that title"* rather than guessing when a title isn't found.

---

## Limitations

- Free-tier API rate limits may restrict query volume during heavy testing.
- Very new or obscure titles may have incomplete data in free databases.
- Recommendation quality depends on how well genre/tag metadata is structured in the source APIs.

---

## Roadmap Ideas

- Add streaming-availability lookup via a dedicated API
- Add poster/image rendering in the chat UI
- Add a local vector store (Chroma/FAISS) for caching frequently asked titles
- Support multi-title comparison queries natively

---

## License

This project is for educational/demonstration purposes. All data is sourced from third-party public APIs (TMDB, OMDb, Jikan/MyAnimeList) — please review each provider's terms of use before deploying publicly.
