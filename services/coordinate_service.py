from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from services.audit_service import log_action
from services.database import clear_data_cache, get_db

COORDINATE_COLUMNS = [
    "nama_upt", "jenis_upt", "kelas_upt", "subjenis_upt", "provinsi", "kanwil",
    "kabupaten_kota", "alamat", "latitude", "longitude", "coordinate_quality",
    "coordinate_source", "coordinate_score", "coordinate_verified_at",
    "coordinate_verified_by", "aktif", "catatan_verifikasi",
]

COLUMN_ALIASES = {
    "nama upt": "nama_upt", "nama_upt": "nama_upt", "upt": "nama_upt",
    "jenis": "jenis_upt", "jenis upt": "jenis_upt", "jenis_upt": "jenis_upt",
    "kelas": "kelas_upt", "kelas upt": "kelas_upt", "kelas_upt": "kelas_upt",
    "subjenis": "subjenis_upt", "subjenis upt": "subjenis_upt", "subjenis_upt": "subjenis_upt",
    "provinsi": "provinsi", "kanwil": "kanwil", "kabupaten/kota": "kabupaten_kota",
    "kabupaten kota": "kabupaten_kota", "kabupaten_kota": "kabupaten_kota",
    "alamat": "alamat", "latitude": "latitude", "lat": "latitude",
    "longitude": "longitude", "long": "longitude", "lng": "longitude",
    "kualitas koordinat": "coordinate_quality", "coordinate_quality": "coordinate_quality",
    "sumber koordinat": "coordinate_source", "coordinate_source": "coordinate_source",
    "skor koordinat": "coordinate_score", "coordinate_score": "coordinate_score",
    "aktif": "aktif", "catatan": "catatan_verifikasi", "catatan_verifikasi": "catatan_verifikasi",
}


def normalize_coordinate_import(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    renamed: dict[str, str] = {}
    for col in out.columns:
        key = " ".join(str(col).strip().casefold().replace("_", " ").split())
        renamed[col] = COLUMN_ALIASES.get(key, str(col).strip())
    out = out.rename(columns=renamed)
    if "nama_upt" not in out.columns:
        raise ValueError("File wajib memiliki kolom Nama UPT atau nama_upt.")
    for col in COORDINATE_COLUMNS:
        if col not in out.columns:
            out[col] = None
    out["nama_upt"] = out["nama_upt"].fillna("").astype(str).str.strip()
    out = out[out["nama_upt"] != ""].copy()
    out["latitude"] = pd.to_numeric(out["latitude"], errors="coerce")
    out["longitude"] = pd.to_numeric(out["longitude"], errors="coerce")
    out["coordinate_score"] = pd.to_numeric(out["coordinate_score"], errors="coerce")
    out["aktif"] = out["aktif"].fillna(True).astype(str).str.casefold().map(
        {"true": True, "1": True, "ya": True, "aktif": True, "false": False, "0": False, "tidak": False, "nonaktif": False}
    ).fillna(True)
    out["coordinate_quality"] = out["coordinate_quality"].fillna("").astype(str).str.strip()
    out.loc[out["coordinate_quality"] == "", "coordinate_quality"] = "Hasil impor—perlu verifikasi"
    return out[COORDINATE_COLUMNS]


def _json_safe(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _save_rows_without_unique_constraint(rows: list[dict[str, Any]]) -> None:
    db = get_db()
    if db is None:
        raise RuntimeError("Supabase belum terhubung.")
    response = db.table("upt").select("nama_upt").execute()
    existing_names = {
        " ".join(str(r.get("nama_upt") or "").split()).casefold(): str(r.get("nama_upt") or "").strip()
        for r in (response.data or []) if str(r.get("nama_upt") or "").strip()
    }
    inserts: list[dict[str, Any]] = []
    for row in rows:
        name = str(row.get("nama_upt") or "").strip()
        key = " ".join(name.split()).casefold()
        payload = {k: v for k, v in row.items() if k != "nama_upt"}
        if key in existing_names:
            db.table("upt").update(payload).eq("nama_upt", existing_names[key]).execute()
        else:
            inserts.append(row)
            existing_names[key] = name
    for start in range(0, len(inserts), 200):
        db.table("upt").insert(inserts[start:start + 200]).execute()
    clear_data_cache()


def import_coordinates(df: pd.DataFrame, actor_username: str, actor_role: str) -> int:
    normalized = normalize_coordinate_import(df)
    rows: list[dict[str, Any]] = []
    for record in normalized.to_dict(orient="records"):
        rows.append({key: _json_safe(value) for key, value in record.items()})
    _save_rows_without_unique_constraint(rows)
    log_action(
        "import_coordinates", "upt", actor_username=actor_username, actor_role=actor_role,
        metadata={"rows": len(rows)},
    )
    return len(rows)


def save_coordinate(
    nama_upt: str,
    payload: dict[str, Any],
    actor_username: str,
    actor_role: str,
    verify: bool = False,
) -> None:
    prepared = {key: _json_safe(value) for key, value in payload.items() if key in COORDINATE_COLUMNS}
    prepared["nama_upt"] = nama_upt
    if verify:
        prepared.update({
            "coordinate_quality": "Terverifikasi",
            "coordinate_verified_at": datetime.now(timezone.utc).isoformat(),
            "coordinate_verified_by": actor_username,
        })
    _save_rows_without_unique_constraint([prepared])
    log_action(
        "verify_coordinate" if verify else "update_coordinate",
        "upt",
        nama_upt,
        actor_username,
        actor_role,
        {"fields": sorted(prepared)},
    )
