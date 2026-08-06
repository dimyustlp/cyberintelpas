from __future__ import annotations

import base64
import io
from datetime import datetime
import pandas as pd
import qrcode
from jinja2 import Template
from weasyprint import HTML


def generate_qr_code_base64(url: str) -> str:
    """Membuat QR Code dari URL berita dan mengembalikan string Base64 untuk disisipkan ke HTML."""
    if not url:
        return ""
    qr = qrcode.QRCode(version=1, box_size=4, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        @page { size: A4 portrait; margin: 15mm; }
        body { font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 10pt; color: #333; line-height: 1.4; }
        .header { text-align: center; border-bottom: 2px solid #1a365d; padding-bottom: 10px; margin-bottom: 15px; }
        .header h2 { margin: 0; color: #1a365d; font-size: 14pt; text-transform: uppercase; }
        .header h3 { margin: 3px 0; color: #4a5568; font-size: 11pt; }
        .header p { margin: 0; font-size: 8pt; color: #718096; }
        
        .stats-table { width: 100%; border-collapse: collapse; margin-bottom: 15px; }
        .stats-table td { border: 1px solid #cbd5e0; padding: 8px; text-align: center; }
        .stat-val { font-size: 14pt; font-weight: bold; }
        .pos { color: #2f855a; }
        .neg { color: #c53030; }
        
        .data-table { width: 100%; border-collapse: collapse; margin-bottom: 15px; font-size: 8.5pt; }
        .data-table th { background-color: #2b6cb0; color: white; padding: 6px; border: 1px solid #2b6cb0; text-align: left; }
        .data-table td { padding: 5px; border: 1px solid #e2e8f0; text-align: left; vertical-align: top; }
        .data-table tr:nth-child(even) { background-color: #f7fafc; }
        
        .badge-pos { background-color: #c6f6d5; color: #22543d; padding: 2px 6px; border-radius: 4px; font-weight: bold; }
        .badge-neg { background-color: #fed7d7; color: #742a2a; padding: 2px 6px; border-radius: 4px; font-weight: bold; }
        
        .page-break { page-break-before: always; }
        
        .kliping-card { border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; margin-bottom: 15px; background: #fff5f5; }
        .kliping-title { font-weight: bold; color: #9b2c2c; font-size: 11pt; margin-bottom: 5px; }
        .kliping-meta { font-size: 8pt; color: #4a5568; margin-bottom: 10px; }
        .kliping-summary { font-size: 9pt; }
    </style>
</head>
<body>

    <div class="header">
        <h2>Direktorat Jenderal Pemasyarakatan</h2>
        <h3>LAPORAN HARIAN MONITORING PEMBERITAAN UPT PEMASYARAKATAN</h3>
        <p>Periode: {{ periode_laporan }} | Sumber Data: Command Center Cyber-Intelpas</p>
    </div>

    <table class="stats-table">
        <tr>
            <td><div class="stat-val">{{ total_berita }}</div><div>TOTAL BERITA</div></td>
            <td><div class="stat-val pos">{{ total_positif }}</div><div>SENTIMEN POSITIF</div></td>
            <td><div class="stat-val neg">{{ total_negatif }}</div><div>SENTIMEN NEGATIF</div></td>
            <td><div class="stat-val pos">{{ pct_positif }}%</div><div>% POSITIF</div></td>
            <td><div class="stat-val neg">{{ pct_negatif }}%</div><div>% NEGATIF</div></td>
        </tr>
    </table>

    <h4 style="margin-bottom: 5px;">Sebaran Pemberitaan Bersentimen Negatif</h4>
    <table class="data-table">
        <thead>
            <tr><th width="8%">No</th><th>Kantor Wilayah / UPT Terdampak</th><th width="15%">Jumlah</th></tr>
        </thead>
        <tbody>
            {% for item in sebaran_negatif %}
            <tr>
                <td>{{ loop.index }}</td>
                <td><b>{{ item.kanwil }}</b> - {{ item.upt }}</td>
                <td><span class="badge-neg">{{ item.jumlah }}</span></td>
            </tr>
            {% else %}
            <tr><td colspan="3" style="text-align:center;">Nihil temuan berita negatif pada periode ini.</td></tr>
            {% endfor %}
        </tbody>
    </table>

    <div class="page-break"></div>
    <h3>LAMPIRAN TEMUAN PEMBERITAAN HARIAN</h3>
    <table class="data-table">
        <thead>
            <tr>
                <th width="5%">No</th>
                <th width="15%">Media</th>
                <th>Judul Berita</th>
                <th width="12%">Sentimen</th>
                <th width="25%">UPT</th>
            </tr>
        </thead>
        <tbody>
            {% for row in daftar_berita %}
            <tr>
                <td>{{ loop.index }}</td>
                <td>{{ row.media }}</td>
                <td><a href="{{ row.link }}" style="text-decoration:none; color:#2b6cb0;">{{ row.judul }}</a></td>
                <td>
                    {% if row.sentimen == 'Positif' %}
                    <span class="badge-pos">Positif</span>
                    {% else %}
                    <span class="badge-neg">Negatif</span>
                    {% endif %}
                </td>
                <td>{{ row.nama_upt }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    {% if berita_negatif_list %}
    <div class="page-break"></div>
    <h3 style="color: #9b2c2c;">DETAIL KLIPING & RINGKASAN EKSEKUTIF ISU NEGATIF</h3>
    {% for item in berita_negatif_list %}
    <div class="kliping-card">
        <div class="kliping-title">{{ item.judul }}</div>
        <div class="kliping-meta">
            <b>Media:</b> {{ item.media }} | <b>UPT:</b> {{ item.nama_upt }} | <b>Terbit:</b> {{ item.tanggal_publikasi }}
        </div>
        <table width="100%" style="border-collapse:collapse;">
            <tr>
                <td style="border:none; padding:0; vertical-align:top;" width="78%">
                    <div class="kliping-summary">
                        <b>Ringkasan Eksekutif AI (Kronologi & Bukti):</b><br>
                        <p style="white-space: pre-line; margin-top: 5px;">{{ item.ringkasan }}</p>
                    </div>
                </td>
                <td style="border:none; padding:0; text-align:center; vertical-align:top;" width="22%">
                    {% if item.qr_code_base64 %}
                    <img src="data:image/png;base64,{{ item.qr_code_base64 }}" width="95"><br>
                    <span style="font-size:7pt; color:#718096;">Scan Tautan Berita</span>
                    {% endif %}
                </td>
            </tr>
        </table>
    </div>
    {% endfor %}
    {% endif %}

</body>
</html>
"""


def create_daily_pdf_bytes(df_news: pd.DataFrame, periode_label: str) -> bytes:
    """Mengolah DataFrame berita dan merender PDF menjadi format bytes."""
    total = len(df_news)
    positif = len(df_news[df_news["sentimen"] == "Positif"]) if total > 0 else 0
    negatif = len(df_news[df_news["sentimen"] == "Negatif"]) if total > 0 else 0

    pct_pos = round((positif / total * 100), 2) if total > 0 else 0
    pct_neg = round((negatif / total * 100), 2) if total > 0 else 0

    # Sebaran isu negatif per UPT
    df_neg = df_news[df_news["sentimen"] == "Negatif"] if total > 0 else pd.DataFrame()
    sebaran_neg = []
    if not df_neg.empty:
        grouped = df_neg.groupby(["nama_upt"]).size().reset_index(name="jumlah")
        for _, row in grouped.iterrows():
            sebaran_neg.append({
                "kanwil": "Wilayah Terdampak",  # Dapat disesuaikan dengan mapping relasi Kanwil Anda
                "upt": row["nama_upt"],
                "jumlah": row["jumlah"],
            })

    # Siapkan kliping negatif + QR code
    berita_negatif_list = []
    if not df_neg.empty:
        for _, row in df_neg.iterrows():
            item = row.to_dict()
            item["qr_code_base64"] = generate_qr_code_base64(str(row.get("link", "")))
            berita_negatif_list.append(item)

    template = Template(HTML_TEMPLATE)
    html_out = template.render(
        periode_laporan=periode_label,
        total_berita=total,
        total_positif=positif,
        total_negatif=negatif,
        pct_positif=pct_pos,
        pct_negatif=pct_neg,
        sebaran_negatif=sebaran_neg,
        daftar_berita=df_news.to_dict("records") if total > 0 else [],
        berita_negatif_list=berita_negatif_list,
    )

    pdf_bytes = HTML(string=html_out).write_pdf()
    return pdf_bytes