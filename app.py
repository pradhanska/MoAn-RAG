"""CineAI — Streamlit chat UI (dark cinema + anime aesthetic).

Run:  streamlit run app.py
"""

from __future__ import annotations

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import streamlit as st

from moan import ask
from moan.pipeline import MODE_AUTO, MODE_LLM, MODE_TEMPLATE

st.set_page_config(
    page_title="CineAI — Movie & Anime Q&A",
    page_icon="🎬",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ── CineAI theme (mirrors index.html design tokens) ──────────────────────────
st.markdown(
    """
    <style>
    .stApp {
        background: radial-gradient(60% 50% at 15% 0%, rgba(230,59,122,0.10), transparent 60%),
                    radial-gradient(55% 45% at 88% 10%, rgba(123,92,250,0.10), transparent 60%),
                    #0D0D14;
        color: #F0EFF5;
    }
    h1, h2, h3 { font-family: 'Bebas Neue', sans-serif; letter-spacing: .04em; }
    .cine-header { text-align:center; padding: 1.2rem 0 .4rem; }
    .cine-title {
        font-family:'Bebas Neue', sans-serif; font-size: 3.2rem; letter-spacing:.06em;
        background: linear-gradient(90deg, #E63B7A, #7B5CFA);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text; margin-bottom:.1rem;
    }
    .cine-tag { color:#6B6A80; font-size:.9rem; }
    .cine-sources { font-size:.78rem; color:#6B6A80; margin-top:.35rem; }
    .cine-sources a { color:#7B5CFA; text-decoration:none; }
    .cine-sources a:hover { color:#E63B7A; }
    [data-testid="stChatMessage"] { background: rgba(19,19,31,0.85); border:1px solid rgba(255,255,255,0.07); }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="cine-header"><div class="cine-title">CINEAI</div>'
            '<div class="cine-tag">movie &amp; anime Q&amp;A · grounded in real data — no hallucinations</div></div>',
            unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ engine")
    mode = st.radio("answer engine", ["auto", "llm", "template"], index=0,
                    help="auto: LLM if a key is set, else the local grounded template")
    llm_key = bool(os.getenv("LLM_API_KEY", "").strip())
    tmdb_key = bool(os.getenv("TMDB_API_KEY", "").strip())
    omdb_key = bool(os.getenv("OMDB_API_KEY", "").strip())
    st.markdown("#### providers")
    st.caption(f"LLM   {'✅' if llm_key else '— (optional)'}")
    st.caption(f"TMDB  {'✅' if tmdb_key else '— (movie searches)'}")
    st.caption(f"OMDb  {'✅' if omdb_key else '— (movie searches)'}")
    st.caption("Jikan · TVMaze  ✅ always on (keyless)")
    if st.button("clear chat"):
        st.session_state.messages = []
    st.markdown("---")
    st.caption("try: \"who directed Spirited Away\" · "
               "\"how many episodes does One Piece have\" · "
               "\"recommend an anime like Death Note\"")

MODE_MAP = {"auto": MODE_AUTO, "llm": MODE_LLM, "template": MODE_TEMPLATE}

# ── Chat ─────────────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Ask me anything about a movie, show, anime or manga — I'll back every answer with a source. 🎬"}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("sources"):
            src = " · ".join(f"[{s['provider']}] [{s['title']}]({s['url']})" for s in msg["sources"])
            st.markdown(f'<div class="cine-sources">source: {src}</div>', unsafe_allow_html=True)

if prompt := st.chat_input("Ask about a movie, show, anime or manga…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("looking it up…"):
            answer = ask(prompt, mode=MODE_MAP[mode])
        st.markdown(answer.answer)
        if answer.sources:
            src = " · ".join(f"[{s.provider}] [{s.title}]({s.url})" for s in answer.sources)
            st.markdown(f'<div class="cine-sources">source: {src}</div>', unsafe_allow_html=True)
        with st.expander(f"context used · engine: {answer.provider}"):
            st.caption(answer.context or "(no context retrieved)")

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer.answer,
        "sources": [s.to_dict() for s in answer.sources],
    })