from __future__ import annotations

import mimetypes
import uuid
from datetime import datetime, timezone
from pathlib import Path

from services.audit_service import log_action
from services.database import get_db, table_exists

BUCKET = "berita-bukti"
MAX_BYTES = 10 * 1024 * 1024
MAX_FILES_PER_NEWS = 5
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}


def validate_attachment(filename: str, data: bytes) -> None:
    ext = Path(filename or "").suffix.casefold()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Lampiran hanya mendukung JPG, JPEG, PNG, dan PDF.")
    if len(data) > MAX_BYTES:
        raise ValueError("Ukuran lampiran maksimal 10 MB per file.")
    signatures = {
        ".jpg": (b"\xff\xd8\xff",),
        ".jpeg": (b"\xff\xd8\xff",),
        ".png": (b"\x89PNG\r\n\x1a\n",),
        ".pdf": (b"%PDF",),
    }
    if not any(data.startswith(signature) for signature in signatures[ext]):
        raise ValueError("Isi file tidak sesuai dengan ekstensi JPG, PNG, atau PDF yang dipilih.")


def upload_attachment(
    berita_id: str,
    filename: str,
    data: bytes,
    actor_username: str,
    actor_role: str,
    description: str = "",
) -> str:
    validate_attachment(filename, data)
    if not table_exists("berita_attachments"):
        raise RuntimeError("Tabel lampiran belum tersedia. Jalankan migration SQL terbaru.")
    db = get_db()
    if db is None:
        raise RuntimeError("Supabase belum terhubung.")
    existing = (
        db.table("berita_attachments")
        .select("id", count="exact")
        .eq("berita_id", berita_id)
        .is_("deleted_at", "null")
        .execute()
    )
    active_count = int(existing.count or len(existing.data or []))
    if active_count >= MAX_FILES_PER_NEWS:
        raise ValueError("Maksimal 5 lampiran aktif untuk setiap berita.")
    ext = Path(filename).suffix.casefold()
    object_path = f"{berita_id}/{datetime.now(timezone.utc):%Y/%m}/{uuid.uuid4().hex}{ext}"
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    try:
        db.storage.from_(BUCKET).upload(
            object_path,
            data,
            file_options={"content-type": content_type, "upsert": "false"},
        )
    except TypeError:
        db.storage.from_(BUCKET).upload(object_path, data, {"content-type": content_type})
    attachment_id = str(uuid.uuid4())
    db.table("berita_attachments").insert({
        "id": attachment_id,
        "berita_id": berita_id,
        "file_name": Path(filename).name,
        "storage_path": object_path,
        "mime_type": content_type,
        "size_bytes": len(data),
        "description": description.strip(),
        "uploaded_by": actor_username,
    }).execute()
    log_action(
        "upload_attachment", "berita", berita_id, actor_username, actor_role,
        {"attachment_id": attachment_id, "file_name": Path(filename).name, "size_bytes": len(data)},
    )
    return attachment_id


def list_attachments(berita_id: str) -> list[dict]:
    if not table_exists("berita_attachments"):
        return []
    db = get_db()
    if db is None:
        return []
    response = (
        db.table("berita_attachments")
        .select("*")
        .eq("berita_id", berita_id)
        .is_("deleted_at", "null")
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def signed_url(storage_path: str, expires_in: int = 3600) -> str:
    db = get_db()
    if db is None:
        return ""
    try:
        response = db.storage.from_(BUCKET).create_signed_url(storage_path, expires_in)
        if isinstance(response, dict):
            return str(response.get("signedURL") or response.get("signedUrl") or "")
        return str(getattr(response, "signed_url", "") or "")
    except Exception:
        return ""


def archive_attachment(attachment_id: str, actor_username: str, actor_role: str) -> None:
    db = get_db()
    if db is None:
        raise RuntimeError("Supabase belum terhubung.")
    now = datetime.now(timezone.utc).isoformat()
    db.table("berita_attachments").update({
        "deleted_at": now,
        "deleted_by": actor_username,
    }).eq("id", attachment_id).execute()
    log_action("archive_attachment", "berita_attachment", attachment_id, actor_username, actor_role)
