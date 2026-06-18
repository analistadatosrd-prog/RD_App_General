import streamlit as st
import pandas as pd

from services.db import fetch_all
from shared.ui import require_auth, module_header, dataframe_download_csv, show_user_context

require_auth()

module_header(
    "Informe ROI",
    "Visualización y descarga de la tabla rd_tabla_rentas_ideales."
)
show_user_context()

col_accion1, col_accion2 = st.columns([1, 4])

with col_accion1:
    cargar = st.button("Cargar informe ROI", type="primary", use_container_width=True)

if "df_informe_roi" not in st.session_state:
    st.session_state["df_informe_roi"] = pd.DataFrame()

if cargar:
    with st.spinner("Consultando informe ROI..."):
        resultados = fetch_all("SELECT * FROM rd_tabla_rentas_ideales")
        if resultados:
            st.session_state["df_informe_roi"] = pd.DataFrame(resultados)
        else:
            st.session_state["df_informe_roi"] = pd.DataFrame()

df = st.session_state["df_informe_roi"]

if df.empty:
    st.info("No hay datos cargados. Presiona 'Cargar informe ROI'.")
else:
    st.success(f"Se cargaron {len(df)} registros.")

    col_d1, col_d2 = st.columns([1, 3])
    with col_d1:
        dataframe_download_csv(
            df,
            filename="rd_tabla_rentas_ideales.csv",
            label="Descargar CSV"
        )

    st.dataframe(df, use_container_width=True, height=600)
