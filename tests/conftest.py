from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _cache_decorator(*decorator_args, **decorator_kwargs):
    def decorate(func):
        func.clear = lambda: None
        return func
    if decorator_args and callable(decorator_args[0]) and len(decorator_args) == 1 and not decorator_kwargs:
        return decorate(decorator_args[0])
    return decorate


if importlib.util.find_spec("streamlit") is None:
    st = types.ModuleType("streamlit")
    st.cache_data = _cache_decorator
    st.cache_resource = _cache_decorator
    st.error = lambda *args, **kwargs: None
    st.stop = lambda *args, **kwargs: None
    st.secrets = {}
    st.session_state = {}
    sys.modules["streamlit"] = st

if importlib.util.find_spec("supabase") is None:
    supabase = types.ModuleType("supabase")
    supabase.Client = object
    supabase.create_client = lambda *args, **kwargs: None
    supabase_client = types.ModuleType("supabase.client")

    class ClientOptions:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    supabase_client.ClientOptions = ClientOptions
    sys.modules["supabase"] = supabase
    sys.modules["supabase.client"] = supabase_client
