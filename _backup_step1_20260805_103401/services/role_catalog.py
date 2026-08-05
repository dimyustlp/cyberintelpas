from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RoleDefinition:
    code: str
    name: str
    short_description: str
    main_focus: str


ROLE_DEFINITIONS: tuple[RoleDefinition, ...] = (
    RoleDefinition(
        "executive_decision_maker",
        "Pimpinan Pengambil Keputusan",
        "Menerima ringkasan strategis, menetapkan prioritas, memberi arahan, dan memantau penyelesaian tindak lanjut.",
        "Situasi, risiko, keputusan, dan progres tindak lanjut.",
    ),
    RoleDefinition(
        "media_intelligence_analyst",
        "Analis Intelijen Pemberitaan",
        "Menelaah berita, memvalidasi sentimen dan urgensi, memetakan UPT, serta mengelompokkan publikasi ke dalam isu yang sama.",
        "Narasi media, kualitas klasifikasi, tren isu, dan analisis awal.",
    ),
    RoleDefinition(
        "news_data_operator",
        "Operator Akuisisi dan Validasi Data",
        "Menjaga kelancaran data berita masuk, memeriksa link, metadata, sumber, serta mencegah duplikasi publikasi.",
        "Kelengkapan, keunikan, dan kesehatan aliran data.",
    ),
    RoleDefinition(
        "field_verification_officer",
        "Petugas Verifikasi Lapangan",
        "Melaksanakan penugasan ke UPT, mengumpulkan fakta, dokumen dan bukti, lalu menyampaikan laporan lapangan.",
        "Penugasan, fakta lapangan, bukti, dan komitmen perbaikan UPT.",
    ),
    RoleDefinition(
        "evaluation_recommendation_analyst",
        "Analis Evaluasi dan Rekomendasi",
        "Membandingkan narasi media dengan fakta lapangan, menilai dampak, akar masalah, dan menyusun rekomendasi akhir.",
        "Validitas fakta, dampak, akar masalah, dan rekomendasi kebijakan.",
    ),
    RoleDefinition(
        "super_admin",
        "Administrator Utama CYBER-INTELPAS",
        "Mengelola pengguna, izin, konfigurasi, integrasi, keamanan, audit, serta kesehatan seluruh layanan sistem.",
        "Ketersediaan, keamanan, integrasi, error, backup, dan kapasitas sistem.",
    ),
)

ROLE_BY_CODE = {item.code: item for item in ROLE_DEFINITIONS}
ROLE_OPTIONS = {item.name: item.code for item in ROLE_DEFINITIONS}

# Alias menjaga kompatibilitas dengan rilis V5.3 sampai V5.7.
LEGACY_ROLE_ALIASES: dict[str, str] = {
    "executive_viewer": "executive_decision_maker",
    "news_analyst": "media_intelligence_analyst",
    "news_intake": "news_data_operator",
    "pimpinan_eksekutif": "executive_decision_maker",
    "analis_pemberitaan_strategis": "media_intelligence_analyst",
    "operator_akuisisi_data_berita": "news_data_operator",
    "administrator_utama_sistem": "super_admin",
    "admin_pusat": "media_intelligence_analyst",
    "admin_kanwil": "media_intelligence_analyst",
    "operator_upt": "news_data_operator",
    "viewer": "executive_decision_maker",
}


def canonical_role(role: str | None) -> str:
    value = str(role or "").strip()
    return LEGACY_ROLE_ALIASES.get(value, value)


def role_name(role: str | None) -> str:
    code = canonical_role(role)
    definition = ROLE_BY_CODE.get(code)
    return definition.name if definition else code.replace("_", " ").title()


def role_description(role: str | None) -> str:
    code = canonical_role(role)
    definition = ROLE_BY_CODE.get(code)
    return definition.short_description if definition else "Peran belum terdaftar pada katalog CYBER-INTELPAS."
