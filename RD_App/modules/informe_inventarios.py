import streamlit as st
import pandas as pd

from services.db import fetch_all
from shared.ui import require_auth, module_header, dataframe_download_csv, show_user_context

require_auth()

module_header(
    "Informe de inventarios",
    "Visualización y descarga de la tabla rd_tabla_inventarios."
)
show_user_context()

col_accion1, col_accion2 = st.columns([1, 4])

with col_accion1:
    cargar = st.button("Cargar inventarios", type="primary", use_container_width=True)

if "df_inventarios" not in st.session_state:
    st.session_state["df_inventarios"] = pd.DataFrame()

if cargar:
    with st.spinner("Consultando inventarios..."):
        resultados = fetch_all("SELECT * FROM rd_tabla_inventarios")
        if resultados:
            st.session_state["df_inventarios"] = pd.DataFrame(resultados)
        else:
            st.session_state["df_inventarios"] = pd.DataFrame()

df = st.session_state["df_inventarios"]

if df.empty:
    st.info("No hay datos cargados. Presiona 'Cargar inventarios'.")
else:
    st.success(f"Se cargaron {len(df)} registros.")

    col_d1, col_d2 = st.columns([1, 3])
    with col_d1:
        dataframe_download_csv(
            df,
            filename="rd_tabla_inventarios.csv",
            label="Descargar CSV"
        )

    st.dataframe(df, use_container_width=True, height=600)
