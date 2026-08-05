from __future__ import annotations

import streamlit as st

from components.layout import info_panel, page_header
from services.access_control import require_permission, scope_news
from services.ai_service import assistant_answer
from services.auth_service import current_user
from services.database import fetch_news_df, fetch_upt_df
from services.news_service import normalize_status, warning_state

user = require_permission("use_ai")
page_header(
    "AI Assistant",
    "Tanyakan kondisi pemberitaan berdasarkan database internal dan telusuri sumber jawaban.",
    "Conversational Analytics",
)
all_upt = fetch_upt_df()
news = scope_news(fetch_news_df(), user, all_upt)
if not news.empty:
    news = news.copy()
    news["status_verifikasi"] = news["status_verifikasi"].map(normalize_status)
    news["warning_state"] = news.apply(warning_state, axis=1)
    if user.role == "executive_decision_maker":
        news = news[news["status_verifikasi"].eq("Terverifikasi") | news["warning_state"].eq("preliminary")].copy()

verified_only = st.toggle("Gunakan hanya berita terverifikasi", value=True)
analysis_news = news[news["status_verifikasi"].astype(str) == "Terverifikasi"] if verified_only else news

info_panel(
    "Contoh Pertanyaan",
    "Apa yang dapat ditanyakan?",
    "Berita negatif minggu ini • UPT paling aktif • Berita urgensi tinggi/kritis • Kategori dominan • Ringkas isu terverifikasi.",
)

st.session_state.setdefault(
    "assistant_messages",
    [{"role": "assistant", "content": "Selamat datang. Jawaban saya dibatasi pada data SIMBERPAS dalam cakupan akun Anda.", "provider": "Sistem", "sources": []}],
)

for message in st.session_state.assistant_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("provider"):
            st.caption(message["provider"])
        if message.get("sources"):
            with st.expander("Sumber data jawaban"):
                for source in message["sources"]:
                    label = f"[{source.get('source_id')}] {source.get('judul')} — {source.get('nama_upt')}"
                    link = source.get("link")
                    if link:
                        st.markdown(f"- [{label}]({link})")
                    else:
                        st.markdown(f"- {label}")

question = st.chat_input("Tanyakan sesuatu tentang data berita...")
if question:
    st.session_state.assistant_messages.append({"role": "user", "content": question, "sources": []})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Menganalisis data internal..."):
            answer, provider, sources = assistant_answer(question, analysis_news)
        st.markdown(answer)
        st.caption(provider)
        if sources:
            with st.expander("Sumber data jawaban"):
                for source in sources:
                    label = f"[{source.get('source_id')}] {source.get('judul')} — {source.get('nama_upt')}"
                    link = source.get("link")
                    if link:
                        st.markdown(f"- [{label}]({link})")
                    else:
                        st.markdown(f"- {label}")
    st.session_state.assistant_messages.append({
        "role": "assistant", "content": answer, "provider": provider, "sources": sources,
    })
