import io
import pandas as pd
import streamlit as st

from services.db import fetch_all

st.set_page_config(page_title="Informe de Inventarios", page_icon="📦", layout="wide")

with st.container():
    st.markdown('<div class="filter-box">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Filtros</div>', unsafe_allow_html=True)

    f1, f2, f3, f4 = st.columns(4)
    with f1:
        vendedores = ["Todos"]
        if col_vendedor:
            vendedores += sorted(df_base[col_vendedor].dropna().astype(str).unique().tolist())
        filtro_vendedor = st.selectbox("Vendedor", vendedores)

    with f2:
        filtro_sku = st.text_input("SKU")

    with f3:
        filtro_titulo = st.text_input("Título")

    with f4:
        filtro_sku_variante = st.text_input("SKU Variante")

    st.markdown('<div class="filter-actions-row">', unsafe_allow_html=True)
    b1, b2, b3 = st.columns([1, 1, 1])

    with b1:
        st.markdown('<div class="visual-btn">', unsafe_allow_html=True)
        aplicar = st.button("Aplicar filtros", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with b2:
        st.markdown('<div class="visual-btn secondary">', unsafe_allow_html=True)
        limpiar = st.button("Limpiar filtros", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with b3:
        csv_buffer = io.BytesIO()
        st.session_state.inv_filtrado.to_csv(csv_buffer, index=False, encoding="utf-8-sig")

        st.markdown('<div class="visual-btn export">', unsafe_allow_html=True)
        st.download_button(
            "Exportar CSV",
            data=csv_buffer.getvalue(),
            file_name="informe_inventarios.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
