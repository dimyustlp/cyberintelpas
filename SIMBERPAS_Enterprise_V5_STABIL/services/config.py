from __future__ import annotations

from dataclasses import dataclass

import streamlit as st


def get_secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, default)
    except Exception:
        value = default
    return str(value or "").strip()


@dataclass(frozen=True)
class AppConfig:
    supabase_url: str
    supabase_key: str
    access_code: str
    openai_api_key: str
    openai_model: str
    app_name: str = "SIMBERPAS"

    @property
    def has_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key and self.openai_model and "YOUR_" not in self.openai_model)


def get_config() -> AppConfig:
    return AppConfig(
        supabase_url=get_secret("SUPABASE_URL"),
        supabase_key=get_secret("SUPABASE_KEY"),
        access_code=get_secret("ACCESS_CODE"),
        openai_api_key=get_secret("OPENAI_API_KEY"),
        openai_model=get_secret("OPENAI_MODEL"),
    )
