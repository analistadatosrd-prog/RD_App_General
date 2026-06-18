import pandas as pd
import streamlit as st

from services.db import fetch_all

st.title("Informe de Inventarios")
st.caption("Vista de inventario basada únicamente en campos de la tabla SQL.")
st.markdown("---")


def fmt_money(valor):
    try:
        return f"$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "-"


def fmt_int(valor):
    try:
        return f"{int(float(valor)):,}".replace(",", ".")
    except Exception:
        return "-"


def safe_text(v):
    if pd.isna(v):
        return ""
    return str(v)


def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()
    df.columns = [c.strip() for c in df.columns]

    mapeo = {
        "skutituloecom": "sku",
        "tituloecom": "titulo_ecom",
        "skuvariante": "sku_variante",
        "costofijo": "costo_fijo",
        "stockdisponible": "stock_disponible",
        "valorventa30dias": "valorventa30dias",
        "undvendidas30dias": "undvendidas30dias",
        "valorventa7dias": "valorventa7dias",
        "undvendidas7dias": "undvendidas7dias",
        "quiebrestock30dias": "quiebrestock30dias",
        "quiebrestock7dias": "quiebrestock7dias",
        "precioventaunitario": "precioventaunitario",
        "stockvalorizado": "stockvalorizado",
        "vendedor": "vendedor",
    }

    for col_original, col_nueva in mapeo.items():
        if col_original in df.columns and col_nueva not in df.columns:
            df.rename(columns={col_original: col_nueva}, inplace=True)

    return df


def cargar_datos():
    rows = fetch_all("SELECT * FROM informe_inventarios")
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df = normalizar_columnas(df)
    return df


if "inventario_df_base" not in st.session_state:
    st.session_state["inventario_df_base"] = pd.DataFrame()

if "inventario_df_filtrado" not in st.session_state:
    st.session_state["inventario_df_filtrado"] = pd.DataFrame()


if st.session_state["inventario_df_base"].empty:
    df_base = cargar_datos()
    st.session_state["inventario_df_base"] = df_base.copy()
    st.session_state["inventario_df_filtrado"] = df_base.copy()


df_base = st.session_state["inventario_df_base"]

if df_base.empty:
    st.warning("No se encontraron datos en la tabla SQL `informe_inventarios`.")
    st.stop()

columnas_esperadas = [
    "sku",
    "titulo_ecom",
    "sku_variante",
    "costo_fijo",
    "stock_disponible",
    "valorventa30dias",
    "undvendidas30dias",
    "valorventa7dias",
    "undvendidas7dias",
    "quiebrestock30dias",
    "quiebrestock7dias",
    "precioventaunitario",
    "stockvalorizado",
    "vendedor",
]

columnas_presentes = [c for c in columnas_esperadas if c in df_base.columns]

st.markdown("### Filtros")

col1, col2, col3, col4 = st.columns(4)

with col1:
    f_sku = st.text_input("SKU")
    f_titulo = st.text_input("Título")

with col2:
    f_variante = st.text_input("SKU variante")
    vendedores = sorted(df_base["vendedor"].dropna().astype(str).unique().tolist()) if "vendedor" in df_base.columns else []
    f_vendedor = st.selectbox("Vendedor", ["Todos"] + vendedores)

with col3:
    stock_min = st.number_input("Stock mínimo", min_value=0, value=0, step=1)
    stock_max_default = int(pd.to_numeric(df_base["stock_disponible"], errors="coerce").fillna(0).max()) if "stock_disponible" in df_base.columns else 0
    stock_max = st.number_input("Stock máximo", min_value=0, value=max(stock_max_default, 0), step=1)

with col4:
    ventas30_min_default = 0.0
    ventas30_max_default = float(pd.to_numeric(df_base["valorventa30dias"], errors="coerce").fillna(0).max()) if "valorventa30dias" in df_base.columns else 0.0
    ventas30_min = st.number_input("Venta 30 días mínima", min_value=0.0, value=ventas30_min_default, step=1000.0)
    ventas30_max = st.number_input("Venta 30 días máxima", min_value=0.0, value=max(ventas30_max_default, 0.0), step=1000.0)

col_btn1, col_btn2 = st.columns([1, 3])

with col_btn1:
    btn_filtrar = st.button("Aplicar filtros", use_container_width=True)

with col_btn2:
    limite = st.selectbox(
        "Límite visual",
        options=[50, 100, 200, 500, 1000, 2000],
        index=2
    )

if btn_filtrar:
    vista = df_base.copy()

    if f_sku.strip() and "sku" in vista.columns:
        vista = vista[vista["sku"].astype(str).str.contains(f_sku.strip(), case=False, na=False)]

    if f_titulo.strip() and "titulo_ecom" in vista.columns:
        vista = vista[vista["titulo_ecom"].astype(str).str.contains(f_titulo.strip(), case=False, na=False)]

    if f_variante.strip() and "sku_variante" in vista.columns:
        vista = vista[vista["sku_variante"].astype(str).str.contains(f_variante.strip(), case=False, na=False)]

    if f_vendedor != "Todos" and "vendedor" in vista.columns:
        vista = vista[vista["vendedor"].astype(str) == f_vendedor]

    if "stock_disponible" in vista.columns:
        stock_num = pd.to_numeric(vista["stock_disponible"], errors="coerce").fillna(0)
        vista = vista[(stock_num >= stock_min) & (stock_num <= stock_max)]

    if "valorventa30dias" in vista.columns:
        venta30_num = pd.to_numeric(vista["valorventa30dias"], errors="coerce").fillna(0)
        vista = vista[(venta30_num >= ventas30_min) & (venta30_num <= ventas30_max)]

    if limite:
        vista = vista.head(limite)

    st.session_state["inventario_df_filtrado"] = vista.copy()

df_vista = st.session_state["inventario_df_filtrado"]

st.markdown(f"**{len(df_vista)} registros en la vista filtrada**")
st.markdown("---")

if df_vista.empty:
    st.info("No hay registros para los filtros seleccionados.")
    st.stop()

df_show = df_vista[columnas_presentes].copy()

for col in [
    "costo_fijo",
    "valorventa30dias",
    "valorventa7dias",
    "precioventaunitario",
    "stockvalorizado",
]:
    if col in df_show.columns:
        df_show[col] = df_show[col].apply(fmt_money)

for col in [
    "stock_disponible",
    "undvendidas30dias",
    "undvendidas7dias",
    "quiebrestock30dias",
    "quiebrestock7dias",
]:
    if col in df_show.columns:
        df_show[col] = df_show[col].apply(fmt_int)

for col in df_show.columns:
    if col not in [
        "costo_fijo",
        "valorventa30dias",
        "valorventa7dias",
        "precioventaunitario",
        "stockvalorizado",
        "stock_disponible",
        "undvendidas30dias",
        "undvendidas7dias",
        "quiebrestock30dias",
        "quiebrestock7dias",
    ]:
        df_show[col] = df_show[col].apply(safe_text)

column_config = {}

if "sku" in df_show.columns:
    column_config["sku"] = st.column_config.TextColumn("SKU", width="medium")

if "titulo_ecom" in df_show.columns:
    column_config["titulo_ecom"] = st.column_config.TextColumn("Título", width="large")

if "sku_variante" in df_show.columns:
    column_config["sku_variante"] = st.column_config.TextColumn("SKU variante", width="medium")

if "costo_fijo" in df_show.columns:
    column_config["costo_fijo"] = st.column_config.TextColumn("Costo fijo", width="small")

if "stock_disponible" in df_show.columns:
    column_config["stock_disponible"] = st.column_config.TextColumn("Stock disponible", width="small")

if "valorventa30dias" in df_show.columns:
    column_config["valorventa30dias"] = st.column_config.TextColumn("Valor venta 30 días", width="medium")

if "undvendidas30dias" in df_show.columns:
    column_config["undvendidas30dias"] = st.column_config.TextColumn("Und. vendidas 30 días", width="small")

if "valorventa7dias" in df_show.columns:
    column_config["valorventa7dias"] = st.column_config.TextColumn("Valor venta 7 días", width="medium")

if "undvendidas7dias" in df_show.columns:
    column_config["undvendidas7dias"] = st.column_config.TextColumn("Und. vendidas 7 días", width="small")

if "quiebrestock30dias" in df_show.columns:
    column_config["quiebrestock30dias"] = st.column_config.TextColumn("Quiebre stock 30 días", width="small")

if "quiebrestock7dias" in df_show.columns:
    column_config["quiebrestock7dias"] = st.column_config.TextColumn("Quiebre stock 7 días", width="small")

if "precioventaunitario" in df_show.columns:
    column_config["precioventaunitario"] = st.column_config.TextColumn("Precio venta unitario", width="medium")

if "stockvalorizado" in df_show.columns:
    column_config["stockvalorizado"] = st.column_config.TextColumn("Stock valorizado", width="medium")

if "vendedor" in df_show.columns:
    column_config["vendedor"] = st.column_config.TextColumn("Vendedor", width="medium")

st.dataframe(
    df_show,
    use_container_width=True,
    height=650,
    column_config=column_config,
)

st.markdown("---")

col_res1, col_res2, col_res3, col_res4 = st.columns(4)

with col_res1:
    if "stock_disponible" in df_vista.columns:
        total_stock = pd.to_numeric(df_vista["stock_disponible"], errors="coerce").fillna(0).sum()
        st.metric("Stock total", fmt_int(total_stock))

with col_res2:
    if "stockvalorizado" in df_vista.columns:
        total_stock_val = pd.to_numeric(df_vista["stockvalorizado"], errors="coerce").fillna(0).sum()
        st.metric("Stock valorizado total", fmt_money(total_stock_val))

with col_res3:
    if "valorventa30dias" in df_vista.columns:
        total_venta30 = pd.to_numeric(df_vista["valorventa30dias"], errors="coerce").fillna(0).sum()
        st.metric("Venta total 30 días", fmt_money(total_venta30))

with col_res4:
    if "undvendidas30dias" in df_vista.columns:
        total_und30 = pd.to_numeric(df_vista["undvendidas30dias"], errors="coerce").fillna(0).sum()
        st.metric("Unidades vendidas 30 días", fmt_int(total_und30))
