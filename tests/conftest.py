from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# Lingkungan CI ringan mungkin belum memasang Streamlit. Stub ini hanya aktif
# untuk pengujian unit dan tidak dipakai ketika Streamlit asli tersedia.
try:
    import streamlit  # noqa: F401
except ModuleNotFoundError:
    streamlit_stub = types.ModuleType("streamlit")

    class _SessionState(dict):
        pass

    def _cache_decorator(func=None, **_kwargs):
        def decorate(target):
            target.clear = lambda: None
            return target
        return decorate(func) if callable(func) else decorate

    streamlit_stub.cache_resource = _cache_decorator
    streamlit_stub.cache_data = _cache_decorator
    streamlit_stub.session_state = _SessionState()
    streamlit_stub.secrets = {}
    streamlit_stub.error = lambda *args, **kwargs: None
    streamlit_stub.warning = lambda *args, **kwargs: None
    streamlit_stub.info = lambda *args, **kwargs: None
    streamlit_stub.success = lambda *args, **kwargs: None
    streamlit_stub.caption = lambda *args, **kwargs: None
    streamlit_stub.stop = lambda *args, **kwargs: None
    streamlit_stub.rerun = lambda *args, **kwargs: None
    sys.modules["streamlit"] = streamlit_stub
