import streamlit as st
import pandas as pd

from shared.ui import require_auth, module_header, dataframe_download_csv, show_user_context

require_auth()

module_header(
    "Informe de costos Foxy",
    "Consulta directa de costos por ml_id desde EcomExperts."
)
show_user_context()

st.info(
    "Este módulo quedó preparado dentro de la estructura general. "
    "En el siguiente paso integraremos la lógica real de consulta a Ecom."
)

if "df_costos_foxy" not in st.session_state:
    st.session_state["df_costos_foxy"] = pd.DataFrame()

col1, col2 = st.columns([1, 4])

with col1:
    consultar = st.button("Consultar costos Foxy", type="primary", use_container_width=True)

if consultar:
    with st.spinner("Preparando consulta de costos Foxy..."):
        # Placeholder temporal.
        # Aquí conectaremos la lógica real que ya tienes en el siguiente paso.
        st.session_state["df_costos_foxy"] = pd.DataFrame()

df = st.session_state["df_costos_foxy"]

if df.empty:
    st.warning("Aún no hay datos cargados en este módulo.")
else:
    st.success(f"Se cargaron {len(df)} registros.")
    col_d1, col_d2 = st.columns([1, 3])
    with col_d1:
        dataframe_download_csv(
            df,
            filename="informe_costos_foxy.csv",
            label="Descargar CSV"
        )

    st.dataframe(df, use_container_width=True, height=600)
