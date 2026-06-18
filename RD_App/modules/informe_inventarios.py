import pandas as pd
import streamlit as st

from services.db import fetch_all

st.title("Inventarios")
st.caption("Consulta, filtra y descarga inventario en formato CSV.")
st.markdown("---")


def fmt_num(valor, dec=0):
    try:
        if dec == 0:
            return f"{float(valor):,.0f}".replace(",", ".")
        return f"{float(valor):,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "-"


def fmt_money(valor):
    try:
        return f"$ {float(valor):,.0f}".replace(",", ".")
    except Exception:
        return "-"


def normalizar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()

    rename_map = {
        "skuasociados": "sku",
        "sku_asociados": "sku",
        "titulo_producto": "titulo_ecom",
        "tituloecom": "titulo_ecom",
        "skuvariante": "sku_variante",
        "stockdisponible": "stock_disponible",
        "stockvalorizado": "stock_valorizado",
        "valorventa30dias": "valor_venta_30_dias",
        "undvendidas30dias": "und_vendidas_30_dias",
        "valorventa7dias": "valor_venta_7_dias",
        "undvendidas7dias": "und_vendidas_7_dias",
        "quiebrestock30dias": "quiebre_stock_30_dias",
        "quiebrestock7dias": "quiebre_stock_7_dias",
        "precioventaunitario": "precio_venta_unitario",
        "costofijo": "costo_fijo",
    }

    for old, new in rename_map.items():
        if old in df.columns and new not in df.columns:
            df.rename(columns={old: new}, inplace=True)

    return df


def ensure_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
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
        vista = vista[vista["vendedor"].astype(str) == f_vendedor]

    if solo_con_stock == "Si" and "stock_disponible" in vista.columns:
        vista = vista[pd.to_numeric(vista["stock_disponible"], errors="coerce").fillna(0) > 0]

    elif solo_con_stock == "No" and "stock_disponible" in vista.columns:
        vista = vista[pd.to_numeric(vista["stock_disponible"], errors="coerce").fillna(0) <= 0]

    return vista


def render_kpis(df: pd.DataFrame):
    df_num = ensure_numeric(
        df,
        [
            "stock_disponible",
            "stock_valorizado",
            "valor_venta_30_dias",
            "und_vendidas_30_dias",
            "valor_venta_7_dias",
            "und_vendidas_7_dias",
            "quiebre_stock_30_dias",
            "quiebre_stock_7_dias",
        ],
    )

    total_skus = len(df_num)

    stock_total = df_num["stock_disponible"].fillna(0).sum() if "stock_disponible" in df_num.columns else 0
    stock_valorizado = df_num["stock_valorizado"].fillna(0).sum() if "stock_valorizado" in df_num.columns else 0
    venta_30 = df_num["valor_venta_30_dias"].fillna(0).sum() if "valor_venta_30_dias" in df_num.columns else 0
    und_30 = df_num["und_vendidas_30_dias"].fillna(0).sum() if "und_vendidas_30_dias" in df_num.columns else 0
    venta_7 = df_num["valor_venta_7_dias"].fillna(0).sum() if "valor_venta_7_dias" in df_num.columns else 0
    und_7 = df_num["und_vendidas_7_dias"].fillna(0).sum() if "und_vendidas_7_dias" in df_num.columns else 0
    quiebres_30 = df_num["quiebre_stock_30_dias"].fillna(0).sum() if "quiebre_stock_30_dias" in df_num.columns else 0

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.metric("SKUs en vista", fmt_num(total_skus))
    with c2:
        st.metric("Stock total", fmt_num(stock_total))
    with c3:
        st.metric("Stock valorizado", fmt_money(stock_valorizado))
    with c4:
        st.metric("Venta 30 días", fmt_money(venta_30))
    with c5:
        st.metric("Unidades 30 días", fmt_num(und_30))
    with c6:
        st.metric("Quiebres 30 días", fmt_num(quiebres_30))

    c7, c8, c9 = st.columns(3)
    with c7:
        st.info(f"Venta 7 días: {fmt_money(venta_7)}")
    with c8:
        st.info(f"Unidades 7 días: {fmt_num(und_7)}")
    with c9:
        vendedores = df["vendedor"].nunique() if "vendedor" in df.columns else 0
        st.info(f"Vendedores en vista: {fmt_num(vendedores)}")


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

st.markdown("### Panel de control")

render_kpis(st.session_state.inventario_filtrado if not st.session_state.inventario_filtrado.empty else df_base)

st.markdown("---")
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

col5, col6, col7 = st.columns(3)
with col5:
    solo_con_stock = st.selectbox("Solo con stock", ["Todos", "Si", "No"])
with col6:
    limite = st.selectbox(
        "Límite de resultados",
        options=[50, 100, 200, 300, 500, 1000, 5000],
        index=3
    )
with col7:
    st.write("")
    st.write("")

col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])

with col_btn1:
    btn_filtrar = st.button("Aplicar filtros", type="primary", use_container_width=True)

with col_btn2:
    btn_limpiar = st.button("Limpiar filtros", use_container_width=True)

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

if btn_limpiar:
    df_reset = df_base.head(limite) if limite else df_base.copy()
    st.session_state.inventario_filtrado = df_reset.copy()
    st.rerun()

df_vista = st.session_state.inventario_filtrado.copy()

st.markdown("---")

col_acc1, col_acc2, col_acc3 = st.columns([1.2, 1.2, 4])
with col_acc1:
    csv_data = df_vista.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="Descargar CSV",
        data=csv_data,
        file_name="inventario_filtrado.csv",
        mime="text/csv",
        use_container_width=True,
    )
with col_acc2:
    st.button("Actualizar vista", disabled=True, use_container_width=True)
with col_acc3:
    st.caption(f"Registros actuales: {len(df_vista)}")

if df_vista.empty:
    st.info("No hay resultados para los filtros seleccionados.")
    st.stop()

st.markdown("### Detalle de inventario")

df_show = df_vista.copy()

df_show = ensure_numeric(
    df_show,
    [
        "costo_fijo",
        "stock_disponible",
        "valor_venta_30_dias",
        "und_vendidas_30_dias",
        "valor_venta_7_dias",
        "und_vendidas_7_dias",
        "quiebre_stock_30_dias",
        "quiebre_stock_7_dias",
        "precio_venta_unitario",
        "stock_valorizado",
    ],
)

cols_inicio = [c for c in ["sku", "titulo_ecom", "sku_variante", "vendedor"] if c in df_show.columns]
otras_cols = [c for c in df_show.columns if c not in cols_inicio]
df_show = df_show[cols_inicio + otras_cols]

for col in [
    "costo_fijo",
    "valor_venta_30_dias",
    "valor_venta_7_dias",
    "precio_venta_unitario",
    "stock_valorizado",
]:
    if col in df_show.columns:
        df_show[col] = df_show[col].apply(fmt_money)

for col in [
    "stock_disponible",
    "und_vendidas_30_dias",
    "und_vendidas_7_dias",
    "quiebre_stock_30_dias",
    "quiebre_stock_7_dias",
]:
    if col in df_show.columns:
        df_show[col] = df_show[col].apply(fmt_num)

st.dataframe(
    df_show,
    use_container_width=True,
    height=650,
    column_config={
        "sku": st.column_config.TextColumn("SKU", width="medium"),
        "titulo_ecom": st.column_config.TextColumn("Título", width="large"),
        "sku_variante": st.column_config.TextColumn("SKU variante", width="medium"),
        "vendedor": st.column_config.TextColumn("Vendedor", width="medium"),
    },
)
