import ast
from pathlib import Path


def test_sync_python_modules_compile():
    root = Path(__file__).resolve().parents[1]
    for rel in ["pages/sinkronisasi_spreadsheet.py", "services/sheet_sync_service.py"]:
        ast.parse((root / rel).read_text(encoding="utf-8"))


def test_migration_contains_public_csv_objects():
    root = Path(__file__).resolve().parents[1]
    sql = (root / "sql/migration_v5_6_public_csv_sync.sql").read_text(encoding="utf-8")
    assert "sheet_sync_log" in sql
    assert "source_record_key" in sql
    assert "berita_source_record_key_unique_idx" in sql


def test_edge_function_uses_public_csv_and_never_writes_google_sheet():
    root = Path(__file__).resolve().parents[1]
    source = (root / "supabase/functions/sheet-sync/index.ts").read_text(encoding="utf-8")
    assert "pub?output=csv" in source
    assert "readPublishedCsv" in source
    assert "parseCsv" in source
    assert "upsert" in source
    assert "x-sync-token" in source
    assert "spreadsheets.readonly" not in source
    assert "GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY" not in source
    assert "SpreadsheetApp" not in source
    assert "values.update" not in source


def test_cron_uses_vault_and_five_minute_schedule():
    root = Path(__file__).resolve().parents[1]
    source = (root / "sql/setup_v5_6_public_csv_cron.sql").read_text(encoding="utf-8")
    assert "*/5 * * * *" in source
    assert "vault.decrypted_secrets" in source
    assert "sheet-sync" in source


def test_public_csv_url_is_configured():
    root = Path(__file__).resolve().parents[1]
    source = (root / ".streamlit/secrets.toml.example").read_text(encoding="utf-8")
    assert "PUBLIC_SHEET_CSV_URL" in source
    assert "2PACX-1vQ0-o2qi5vHXxjnwxPAB4wxtAo8ZdmmVjG-wMvOLSXKjNWXOLCyyR0-1F4aOUn9SnFY8NtFvZeSzaft" in source
