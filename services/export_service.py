from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pandas as pd


def _excel_safe_value(value):
    if value is None:
        return None

    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        if value.tzinfo is not None:
            return value.tz_convert("Asia/Jakarta").tz_localize(None)
        return value

    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return (
                pd.Timestamp(value)
                .tz_convert("Asia/Jakarta")
                .tz_localize(None)
                .to_pydatetime()
            )
        return value

    return value


def excel_safe_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    safe = df.copy()

    for column in safe.columns:
        series = safe[column]

        if isinstance(series.dtype, pd.DatetimeTZDtype):
            safe[column] = series.dt.tz_convert("Asia/Jakarta").dt.tz_localize(None)
            continue

        if pd.api.types.is_datetime64_any_dtype(series.dtype):
            continue

        safe[column] = series.map(_excel_safe_value)

    # Pemeriksaan tambahan untuk kolom tanggal yang umum dari Supabase.
    for column in ["created_at", "updated_at", "tanggal_publikasi", "last_login"]:
        if column not in safe.columns:
            continue
        parsed = pd.to_datetime(safe[column], errors="coerce", utc=True)
        mask = parsed.notna()
        if mask.any():
            converted = parsed.loc[mask].dt.tz_convert("Asia/Jakarta").dt.tz_localize(None)
            safe.loc[mask, column] = converted

    return safe


def excel_bytes(df: pd.DataFrame, sheet_name: str = "Berita") -> bytes:
    safe = excel_safe_dataframe(df)
    output = BytesIO()
    clean_sheet = (sheet_name or "Berita")[:31]

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        safe.to_excel(writer, index=False, sheet_name=clean_sheet)
        sheet = writer.sheets[clean_sheet]
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions

        for column in sheet.columns:
            values = [len(str(cell.value or "")) for cell in column]
            max_len = min(max(values, default=8) + 2, 45)
            sheet.column_dimensions[column[0].column_letter].width = max(10, max_len)

    return output.getvalue()
