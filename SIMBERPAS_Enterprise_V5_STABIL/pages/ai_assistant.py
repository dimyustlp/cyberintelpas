from __future__ import annotations

import streamlit as st

from components.layout import info_panel, page_header
from services.access_control import scope_news
from services.ai_service import assistant_answer
from services.auth_service import current_user
from services.database import fetch_news_df, fetch_upt_df

user = current_user()
page_header("AI Assistant", "Tanyakan kondisi pemberitaan dengan bahasa sehari-hari tanpa menyusun filter manual.", "Conversational Analytics")
news = scope_news(fetch_news_df(), user, fetch_upt_df())

info_panel(
    "Contoh Pertanyaan",
    "Apa yang dapat ditanyakan?",
    "Berita negatif minggu ini • UPT paling aktif • Platform terbanyak • Berita urgensi tinggi • Kategori dominan.",
)

if "assistant_messages" not in st.session_state:
    st.session_state.assistant_messages = [
        {"role": "assistant", "content": "Selamat datang. Saya siap membantu membaca data SIMBERPAS pada cakupan akun Anda.", "provider": "Sistem"}
    ]

for message in st.session_state.assistant_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("provider"):
            st.caption(message["provider"])

question = st.chat_input("Tanyakan sesuatu tentang data berita...")
if question:
    st.session_state.assistant_messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Menganalisis data..."):
            answer, provider = assistant_answer(question, news)
        st.markdown(answer)
        st.caption(provider)
    st.session_state.assistant_messages.append({"role": "assistant", "content": answer, "provider": provider})
