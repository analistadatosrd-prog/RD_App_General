# modules/inventarios.py

import pandas as pd
import streamlit as st

from services.db import fetch_all

st.title("Inventarios")
st.caption("Consulta, filtra y descarga inventario en formato CSV.")
st.markdown("---")


def fmt_number(value):
    try:
        return f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "-"


def normalizar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()

    if "sku" not in df.columns and "sku_asociados" in df.columns:
        df["sku"] = df["sku_asociados"]

    if "titulo_ecom" not in df.columns and "titulo_producto" in df.columns:
        df["titulo_ecom"] = df["titulo_producto"]

    return df


def apply_filtros(
    df: pd.DataFrame,
    f_sku: str,
    f_titulo: str,
    f_variante: str,
    f_vendedor: str,
    solo_con_stock: str,
) -> pd.DataFrame:
    if df.empty:
        return df

    vista = df.copy()

    if f_sku.strip() and "sku" in vista.columns:
        vista = vista[vista["sku"].astype(str).str.contains(f_sku.strip(), case=False, na=False)]

    if f_titulo.strip() and "titulo_ecom" in vista.columns:
        vista = vista[vista["titulo_ecom"].astype(str).str.contains(f_titulo.strip(), case=False, na=False)]

    if f_variante.strip() and "sku_variante" in vista.columns:
        vista = vista[vista["sku_variante"].astype(str).str.contains(f_variante.strip(), case=False, na=False)]

    if f_vendedor != "Todos" and "vendedor" in vista.columns:
        vista = vista[vista["vendedor"] == f_vendedor]

    if solo_con_stock == "Si" and "stock_disponible" in vista.columns:
        vista = vista[pd.to_numeric(vista["stock_disponible"], errors="coerce").fillna(0) > 0]

    if solo_con_stock == "No" and "stock_disponible" in vista.columns:
        vista = vista[pd.to_numeric(vista["stock_disponible"], errors="coerce").fillna(0) <= 0]

    return vista


for key, default in [
    ("inventario_base", pd.DataFrame()),
    ("inventario_filtrado", pd.DataFrame()),
]:
    if key not in st.session_state:
        st.session_state[key] = default

if not st.session_state.get("authenticated"):
    st.error("No hay una sesión autenticada.")
    st.stop()

if st.session_state.inventario_base.empty:
    resultados_pg = fetch_all("SELECT * FROM rd_tabla_inventarios")
    if resultados_pg:
        df_pg = pd.DataFrame(resultados_pg)
        df_pg = normalizar_dataframe(df_pg)
        st.session_state.inventario_base = df_pg.copy()
        st.session_state.inventario_filtrado = df_pg.copy()
    else:
        st.session_state.inventario_base = pd.DataFrame()
        st.session_state.inventario_filtrado = pd.DataFrame()

df_base = st.session_state.inventario_base

if df_base.empty:
    st.warning("No hay datos en rd_tabla_inventarios.")
    st.stop()

vendedores = []
if "vendedor" in df_base.columns:
    vendedores = sorted([str(x) for x in df_base["vendedor"].dropna().unique().tolist() if str(x).strip()])

st.markdown("### Filtros")

col1, col2, col3, col4 = st.columns(4)
with col1:
    f_sku = st.text_input("SKU")
with col2:
    f_titulo = st.text_input("Título")
with col3:
    f_variante = st.text_input("SKU variante")
with col4:
    f_vendedor = st.selectbox("Vendedor", ["Todos"] + vendedores if vendedores else ["Todos"])

col5, col6 = st.columns([1, 2])
with col5:
    solo_con_stock = st.selectbox("Solo con stock", ["Todos", "Si", "No"])
with col6:
    limite = st.selectbox(
        "Límite de resultados",
        options=[50, 100, 200, 300, 500, 1000, 5000],
        index=3
    )

col_btn1, col_btn2 = st.columns([1, 3])
with col_btn1:
    btn_filtrar = st.button("Aplicar filtros", use_container_width=True)

if btn_filtrar:
    df_vista = apply_filtros(
        df_base,
        f_sku,
        f_titulo,
        f_variante,
        f_vendedor,
        solo_con_stock,
    )
    if limite:
        df_vista = df_vista.head(limite)

    st.session_state.inventario_filtrado = df_vista.copy()

df_vista = st.session_state.inventario_filtrado.copy()

st.markdown(f"**{len(df_vista)} registros en la vista**")
st.markdown("---")

if df_vista.empty:
    st.info("No hay resultados para los filtros seleccionados.")
    st.stop()

# Descarga SOLO CSV
csv_data = df_vista.to_csv(index=False).encode("utf-8-sig")

st.download_button(
    label="Descargar CSV",
    data=csv_data,
    file_name="inventario_filtrado.csv",
    mime="text/csv",
    use_container_width=True,
)

st.markdown("---")

df_show = df_vista.copy()

cols_inicio = [c for c in ["sku", "titulo_ecom", "sku_variante", "vendedor"] if c in df_show.columns]
otras_cols = [c for c in df_show.columns if c not in cols_inicio]
df_show = df_show[cols_inicio + otras_cols]

for col in [
    "costo_fijo",
    "valor_venta_30_dias",
    "und_vendidas_30_dias",
    "valor_venta_7_dias",
    "und_vendidas_7_dias",
    "quiebre_stock_30_dias",
    "quiebre_stock_7_dias",
    "precio_venta_unitario",
    "stock_valorizado",
    "stock_disponible",
]:
    if col in df_show.columns:
        try:
            df_show[col] = pd.to_numeric(df_show[col], errors="coerce")
        except Exception:
            pass

st.dataframe(
    df_show,
    use_container_width=True,
    height=650,
)
