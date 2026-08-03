from __future__ import annotations


def classify_rule_based(text: str) -> dict[str, object]:
    t = text.casefold()
    rules = {
        "Keamanan dan Ketertiban": {
            "Pelarian": ["kabur", "melarikan diri", "pelarian"],
            "Kerusuhan": ["kerusuhan", "rusuh", "bentrok", "penyanderaan"],
            "Narkotika": ["narkoba", "narkotika", "sabu", "ganja"],
            "Barang Terlarang": ["barang terlarang", "handphone", "ponsel", "senjata"],
            "Penggeledahan/Razia": ["penggeledahan", "razia"],
        },
        "Pembinaan": {
            "Kemandirian": ["keterampilan", "pelatihan kerja", "produksi", "umkm"],
            "Kepribadian": ["keagamaan", "kerohanian", "pendidikan", "konseling"],
        },
        "Pelayanan": {
            "Kunjungan": ["kunjungan"],
            "Integrasi": ["pembebasan bersyarat", "cuti bersyarat", "integrasi"],
            "Remisi": ["remisi"],
            "Kesehatan": ["kesehatan", "rumah sakit", "sakit"],
        },
        "SDM": {"Kepegawaian": ["pegawai", "petugas", "mutasi", "promosi", "disiplin"]},
        "Sarana dan Prasarana": {"Bangunan/Fasilitas": ["renovasi", "pembangunan", "fasilitas", "sarana"]},
    }
    category, subcategory = "Lainnya", "Umum"
    keywords: list[str] = []
    for cat, subs in rules.items():
        matched = False
        for sub, words in subs.items():
            found = [word for word in words if word in t]
            if found:
                category, subcategory, keywords, matched = cat, sub, found, True
                break
        if matched:
            break
    negative = ["kabur", "meninggal", "kerusuhan", "kebakaran", "narkoba", "narkotika", "penyelundupan", "pungli", "kekerasan", "pelanggaran", "korupsi", "pemerasan", "suap"]
    positive = ["berhasil", "prestasi", "penghargaan", "inovasi", "produktif", "pelatihan", "pembinaan", "kerja sama", "peningkatan"]
    sentiment = "Negatif" if any(w in t for w in negative) else "Positif" if any(w in t for w in positive) else "Netral"
    high = ["kabur", "kerusuhan", "kebakaran", "meninggal", "penyanderaan", "penembakan", "darurat"]
    medium = ["narkoba", "narkotika", "penyelundupan", "pungli", "kekerasan", "penggeledahan", "razia", "pelanggaran"]
    urgency = "Tinggi" if any(w in t for w in high) else "Sedang" if any(w in t for w in medium) else "Rendah"
    attention = "Tinggi" if urgency == "Tinggi" else "Sedang" if sentiment == "Negatif" or urgency == "Sedang" else "Rendah"
    return {
        "kategori": category,
        "subkategori": subcategory,
        "sentimen": sentiment,
        "urgensi": urgency,
        "tingkat_perhatian": attention,
        "kata_kunci": keywords[:8],
        "ai_provider": "rules",
        "ai_confidence": 0.62,
    }
