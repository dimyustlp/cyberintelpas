from __future__ import annotations

import pandas as pd
import streamlit as st

from services.access_control import has_permission
from services.auth_service import current_user
from services.system_health_service import collect_system_health

user = current_user()
if user is None or not has_permission(user, "view_system_health"):
    st.error("Halaman ini hanya tersedia untuk Administrator Utama CYBER-INTELPAS.")
    st.stop()

st.title("System Operations Center")
st.caption("Menampilkan komponen yang normal, memerlukan perhatian, belum dikonfigurasi, atau mengalami error.")

if st.button("Periksa Ulang", type="primary"):
    st.cache_data.clear()
    st.rerun()

health = collect_system_health()
normal = sum(row["status"] == "Normal" for row in health)
warning = sum(row["status"] == "Peringatan" for row in health)
critical = sum(row["status"] == "Kritis" for row in health)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Normal", normal)
c2.metric("Peringatan", warning)
c3.metric("Kritis", critical)
c4.metric("Total Komponen", len(health))

for row in health:
    status = row["status"]
    with st.container(border=True):
        left, right = st.columns([1, 4])
        with left:
            st.markdown(f"### {status}")
        with right:
            st.markdown(f"**{row['component']}**")
            st.write(row["message"])
            if row.get("detail"):
                with st.expander("Detail teknis"):
                    st.code(row["detail"])

st.subheader("Daftar pemeriksaan")
st.dataframe(pd.DataFrame(health), use_container_width=True, hide_index=True)
