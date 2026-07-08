from io import BytesIO

import pandas as pd
import streamlit as st

from services.db import fetch_all

st.set_page_config(
    page_title="Informe ROI",
    page_icon="📈",
    layout="wide",
)

st.title("Informe ROI")
st.caption("Visor de precios idelaes sugeridos")
st.markdown("---")


def init_state():
    defaults = {
        "roi_df_base": pd.DataFrame(),
        "roi_df_vista": pd.DataFrame(),
        "roi_f_ml_id": "",
        "roi_f_titulo_ecom": "",
        "roi_f_sku": "",
        "roi_f_ml_id_sincronizados": "",
        "roi_f_estado_meli": "Todos",
        "roi_f_relacion_catalogo_tradicional": "Todos",
        "roi_f_tipo_oferta": "Todos",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def cargar_datos():
    rows = fetch_all("SELECT * FROM rd_tabla_rentas_ideales")
    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    st.session_state.roi_df_base = df.copy()
    st.session_state.roi_df_vista = df.copy()


def options_from_column(df: pd.DataFrame, col: str):
    if df.empty or col not in df.columns:
        return ["Todos"]
    vals = sorted([str(x) for x in df[col].dropna().unique().tolist() if str(x).strip()])
    return ["Todos"] + vals


def aplicar_filtros():
    df = st.session_state.roi_df_base.copy()

    if df.empty:
        st.session_state.roi_df_vista = df
        return

    f_ml_id = st.session_state.roi_f_ml_id.strip()
    f_titulo = st.session_state.roi_f_titulo_ecom.strip()
    f_sku = st.session_state.roi_f_sku.strip()
    f_ml_sync = st.session_state.roi_f_ml_id_sincronizados.strip()

    f_estado = st.session_state.roi_f_estado_meli
    f_relacion = st.session_state.roi_f_relacion_catalogo_tradicional
    f_tipo = st.session_state.roi_f_tipo_oferta

    if f_ml_id and "ml_id" in df.columns:
        df = df[df["ml_id"].astype(str).str.contains(f_ml_id, case=False, na=False)]

    if f_titulo and "titulo_ecom" in df.columns:
        df = df[df["titulo_ecom"].astype(str).str.contains(f_titulo, case=False, na=False)]

    if f_sku and "sku" in df.columns:
        df = df[df["sku"].astype(str).str.contains(f_sku, case=False, na=False)]

    if f_ml_sync and "ml_id_sincronizados" in df.columns:
        df = df[df["ml_id_sincronizados"].astype(str).str.contains(f_ml_sync, case=False, na=False)]

    if f_estado != "Todos" and "estado_meli" in df.columns:
        df = df[df["estado_meli"].astype(str) == f_estado]

    if f_relacion != "Todos" and "relacion_catalogo_tradicional" in df.columns:
        df = df[df["relacion_catalogo_tradicional"].astype(str) == f_relacion]

    if f_tipo != "Todos" and "tipo_oferta" in df.columns:
        df = df[df["tipo_oferta"].astype(str) == f_tipo]

    st.session_state.roi_df_vista = df.copy()


@st.cache_data
def convert_df_to_csv(df: pd.DataFrame):
    return df.to_csv(index=False).encode("utf-8-sig")


def convert_df_to_excel(df: pd.DataFrame):
    buffer = BytesIO()

    try:
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="informe_roi")
    except Exception:
        try:
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="informe_roi")
        except Exception:
            return None

    return buffer.getvalue()


def limpiar_filtros():
    st.session_state.roi_f_ml_id = ""
    st.session_state.roi_f_titulo_ecom = ""
    st.session_state.roi_f_sku = ""
    st.session_state.roi_f_ml_id_sincronizados = ""
    st.session_state.roi_f_estado_meli = "Todos"
    st.session_state.roi_f_relacion_catalogo_tradicional = "Todos"
    st.session_state.roi_f_tipo_oferta = "Todos"
    aplicar_filtros()


init_state()

if st.session_state.roi_df_base.empty:
    with st.spinner("Cargando tabla rd_tabla_rentas_ideales..."):
        cargar_datos()

df_base = st.session_state.roi_df_base

if df_base.empty:
    st.warning("La tabla rd_tabla_rentas_ideales no tiene datos disponibles.")
    st.stop()

estado_opts = options_from_column(df_base, "estado_meli")
relacion_opts = options_from_column(df_base, "relacion_catalogo_tradicional")
tipo_opts = options_from_column(df_base, "tipo_oferta")

with st.container(border=True):
    st.markdown("### Filtros")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.text_input(
            "ML ID",
            key="roi_f_ml_id",
            placeholder="Buscar ML ID...",
            on_change=aplicar_filtros,
        )
    with c2:
        st.text_input(
            "Título Ecom",
            key="roi_f_titulo_ecom",
            placeholder="Buscar título...",
            on_change=aplicar_filtros,
        )
    with c3:
        st.text_input(
            "SKU",
            key="roi_f_sku",
            placeholder="Buscar SKU...",
            on_change=aplicar_filtros,
        )
    with c4:
        st.text_input(
            "ML ID sincronizados",
            key="roi_f_ml_id_sincronizados",
            placeholder="Buscar sincronizados...",
            on_change=aplicar_filtros,
        )

    d1, d2, d3, d4 = st.columns([1, 1, 1, 1.2])
    with d1:
        st.selectbox(
            "Estado Meli",
            options=estado_opts,
            key="roi_f_estado_meli",
            on_change=aplicar_filtros,
        )
    with d2:
        st.selectbox(
            "Relación catálogo tradicional",
            options=relacion_opts,
            key="roi_f_relacion_catalogo_tradicional",
            on_change=aplicar_filtros,
        )
    with d3:
        st.selectbox(
            "Tipo oferta",
            options=tipo_opts,
            key="roi_f_tipo_oferta",
            on_change=aplicar_filtros,
        )
    with d4:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Limpiar filtros", use_container_width=True):
            limpiar_filtros()
            st.rerun()

aplicar_filtros()
df_vista = st.session_state.roi_df_vista

m1, m2, m3 = st.columns(3)
with m1:
    st.metric("Registros filtrados", len(df_vista))
with m2:
    st.metric("Columnas visibles", len(df_vista.columns))
with m3:
    st.metric("Tabla origen", 1 if not df_base.empty else 0)

st.markdown("### Exportación")
e1, e2, e3 = st.columns([1, 1, 4])

with e1:
    st.download_button(
        label="Descargar CSV",
        data=convert_df_to_csv(df_vista),
        file_name="informe_roi_filtrado.csv",
        mime="text/csv",
        use_container_width=True,
    )

with e2:
    excel_bytes = convert_df_to_excel(df_vista)
    if excel_bytes is not None:
        st.download_button(
            label="Descargar Excel",
            data=excel_bytes,
            file_name="informe_roi_filtrado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    else:
        st.button(
            "Descargar Excel",
            disabled=True,
            use_container_width=True,
            help="No fue posible generar Excel. Revisa si el entorno tiene openpyxl o xlsxwriter.",
        )

st.markdown("---")
st.markdown("### Tabla rd_tabla_rentas_ideales")

st.dataframe(
    df_vista,
    use_container_width=True,
    height=650,
    hide_index=True,
)
