from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

IMPORTS = (
    "from components.role_briefing import render_role_briefing\n"
    "from services.v6_navigation import attach_v6_pages\n"
)


def find_entrypoint(root: Path) -> Path:
    candidates = [root / "app.py", root / "streamlit_app.py"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("app.py atau streamlit_app.py tidak ditemukan pada folder proyek.")


def insert_imports(text: str) -> str:
    missing = [line for line in IMPORTS.splitlines(keepends=True) if line.strip() not in text]
    if not missing:
        return text
    marker = "from styles.theme import inject_global_styles\n"
    if marker not in text:
        raise RuntimeError("Marker import tidak ditemukan. Ikuti docs/PATCH_APP_PY.md secara manual.")
    return text.replace(marker, marker + "".join(missing), 1)


def patch_entrypoint(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    updated = insert_imports(original)

    briefing_call = "render_role_briefing(user)"
    if briefing_call not in updated:
        marker = "render_sidebar_profile(user)\n"
        if marker not in updated:
            raise RuntimeError("Marker render_sidebar_profile(user) tidak ditemukan.")
        updated = updated.replace(marker, marker + "render_role_briefing(user)\n", 1)

    navigation_call = "pages = attach_v6_pages(pages, user)"
    if navigation_call not in updated:
        marker = "navigation = st.navigation(pages, position=\"sidebar\", expanded=True)"
        if marker not in updated:
            marker = "navigation = st.navigation(pages"
            position = updated.find(marker)
            if position < 0:
                raise RuntimeError("Marker st.navigation tidak ditemukan.")
            updated = updated[:position] + navigation_call + "\n\n" + updated[position:]
        else:
            updated = updated.replace(marker, navigation_call + "\n\n" + marker, 1)

    if updated == original:
        print(f"Tidak ada perubahan. {path.name} sudah terintegrasi dengan V6.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(f"{path.name}.backup_sebelum_v6_{timestamp}")
    shutil.copy2(path, backup)
    path.write_text(updated, encoding="utf-8")
    print(f"Berhasil memperbarui {path}")
    print(f"Backup dibuat: {backup}")


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    try:
        entrypoint = find_entrypoint(root)
        patch_entrypoint(entrypoint)
        return 0
    except Exception as exc:
        print(f"GAGAL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
