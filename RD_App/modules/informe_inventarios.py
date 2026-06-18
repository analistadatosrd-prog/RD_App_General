# modules/informe_inventarios.py

import io
from datetime import datetime

import pandas as pd
import streamlit as st

from services.db import fetch_all


st.set_page_config(page_title="Informe de Inventarios", page_icon="📦", layout="wide")

st.title("Informe de Inventarios")
st.caption("Consulta, filtra y exporta inventario valorizado por producto, variante y vendedor.")
st.markdown("---")


# =========================================================
# Helpers
# =========================================================
def fmt_money(valor):
    try:
        return f"$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "-"


def fmt_int(valor):
    try:
        return f"{int(round(float(valor))):,}".replace(",", ".")
    except Exception:
        return "-"


def safe_num(df: pd.DataFrame, col: str, default=0.0):
    if col not in df.columns:
        df[col] = default
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(default)
    return df


def safe_str(df: pd.DataFrame, col: str, default=""):
    if col not in df.columns:
        df[col] = default
    df[col] = df[col].fillna(default).astype(str)
    return df


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()
    original_cols = {c.lower().strip(): c for c in df.columns}

    def pick(*names):
        for n in names:
            if n.lower() in original_cols:
                return original_cols[n.lower()]
        return None

    mapping = {}

    c = pick("sku", "skus", "sku_producto")
    if c:
        mapping[c] = "sku"

    c = pick("titulo_ecom", "titulo", "titulo_producto", "producto")
    if c:
        mapping[c] = "titulo_ecom"

    c = pick("sku_variante", "variante", "skuvariant", "sku_variant")
    if c:
        mapping[c] = "sku_variante"

    c = pick("costo_fijo", "costo", "costo_unitario", "costofijo")
    if c:
        mapping[c] = "costo_fijo"

    c = pick("stock_disponible", "stock", "stock_actual", "disponible")
    if c:
        mapping[c] = "stock_disponible"

    c = pick("valor_venta_30_dias", "valorventa30dias", "valor_venta30dias")
    if c:
        mapping[c] = "valor_venta_30_dias"

    c = pick("und_vendidas_30_dias", "undvendidas30dias", "unidades_30_dias")
    if c:
        mapping[c] = "und_vendidas_30_dias"

    c = pick("valor_venta_7_dias", "valorventa7dias", "valor_venta7dias")
    if c:
        mapping[c] = "valor_venta_7_dias"

    c = pick("und_vendidas_7_dias", "undvendidas7dias", "unidades_7_dias")
    if c:
        mapping[c] = "und_vendidas_7_dias"

    c = pick("quiebre_stock_30_dias", "quiebrestock30dias")
    if c:
        mapping[c] = "quiebre_stock_30_dias"

    c = pick("quiebre_stock_7_dias", "quiebrestock7dias")
    if c:
        mapping[c] = "quiebre_stock_7_dias"

    c = pick("precio_venta_unitario", "precioventaunitario", "precio_venta")
    if c:
        mapping[c] = "precio_venta_unitario"

    c = pick("stock_valorizado", "stockvalorizado", "valor_stock")
    if c:
        mapping[c] = "stock_valorizado"

    c = pick("vendedor", "seller", "canal")
    if c:
        mapping[c] = "vendedor"

    df = df.rename(columns=mapping)

    required_text = ["sku", "titulo_ecom", "sku_variante", "vendedor"]
    required_num = [
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
    ]

    for col in required_text:
        df = safe_str(df, col, "")

    for col in required_num:
        df = safe_num(df, col, 0.0)

    if "stock_valorizado" not in df.columns or df["stock_valorizado"].sum() == 0:
        df["stock_valorizado"] = df["stock_disponible"] * df["costo_fijo"]

    return df


def apply_filters(
    df: pd.DataFrame,
    f_sku: str,
    f_titulo: str,
    f_variante: str,
    f_vendedor: str,
    f_stock: str,
    f_quiebre30: str,
    f_quiebre7: str,
) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()

    if f_sku.strip():
        out = out[out["sku"].str.contains(f_sku.strip(), case=False, na=False)]

    if f_titulo.strip():
        out = out[out["titulo_ecom"].str.contains(f_titulo.strip(), case=False, na=False)]

    if f_variante.strip():
        out = out[out["sku_variante"].str.contains(f_variante.strip(), case=False, na=False)]

    if f_vendedor != "Todos":
        out = out[out["vendedor"] == f_vendedor]

    if f_stock == "Con stock":
        out = out[out["stock_disponible"] > 0]
    elif f_stock == "Sin stock":
        out = out[out["stock_disponible"] <= 0]
    elif f_stock == "Stock negativo":
        out = out[out["stock_disponible"] < 0]

    if f_quiebre30 == "Sí":
        out = out[out["quiebre_stock_30_dias"] > 0]
    elif f_quiebre30 == "No":
        out = out[out["quiebre_stock_30_dias"] <= 0]

    if f_quiebre7 == "Sí":
        out = out[out["quiebre_stock_7_dias"] > 0]
    elif f_quiebre7 == "No":
        out = out[out["quiebre_stock_7_dias"] <= 0]

    return out


def build_export_csv(df: pd.DataFrame) -> bytes:
    export_df = df.copy()
    return export_df.to_csv(index=False).encode("utf-8-sig")


def get_inventory_data() -> pd.DataFrame:
    rows = fetch_all("SELECT * FROM rd_tabla_inventarios")
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return normalize_columns(df)


# =========================================================
# Estado
# =========================================================
if "inv_df_base" not in st.session_state:
    st.session_state.inv_df_base = pd.DataFrame()

if "inv_df_filtrado" not in st.session_state:
    st.session_state.inv_df_filtrado = pd.DataFrame()


# =========================================================
# Carga
# =========================================================
if st.session_state.inv_df_base.empty:
    with st.spinner("Cargando inventarios..."):
        st.session_state.inv_df_base = get_inventory_data()
        st.session_state.inv_df_filtrado = st.session_state.inv_df_base.copy()

df_base = st.session_state.inv_df_base

if df_base.empty:
    st.warning("No se encontraron registros en rd_tabla_inventarios.")
    st.stop()


# =========================================================
# Filtros
# =========================================================
vendedores = sorted([x for x in df_base["vendedor"].dropna().astype(str).unique().tolist() if x])

with st.container():
    st.markdown(
        """
        <div style="
            border:1px solid rgba(120,120,120,0.35);
            border-radius:12px;
            padding:14px 14px 4px 14px;
            margin-bottom:18px;
            background-color: rgba(255,255,255,0.02);
        ">
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Filtros de inventario")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        f_sku = st.text_input("SKU", placeholder="Buscar por SKU")
    with c2:
        f_titulo = st.text_input("Título", placeholder="Buscar por título")
    with c3:
        f_variante = st.text_input("SKU variante", placeholder="Buscar por variante")
    with c4:
        f_vendedor = st.selectbox("Vendedor", ["Todos"] + vendedores)

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        f_stock = st.selectbox("Estado de stock", ["Todos", "Con stock", "Sin stock", "Stock negativo"])
    with c6:
        f_quiebre30 = st.selectbox("Quiebre 30 días", ["Todos", "Sí", "No"])
    with c7:
        f_quiebre7 = st.selectbox("Quiebre 7 días", ["Todos", "Sí", "No"])
    with c8:
        limite = st.selectbox("Límite visual", [100, 250, 500, 1000, 2000], index=2)

    b1, b2, b3 = st.columns([1, 1, 2])
    with b1:
        aplicar = st.button("Aplicar filtros", type="primary", use_container_width=True)
    with b2:
        limpiar = st.button("Limpiar filtros", use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)


if aplicar:
    filtrado = apply_filters(
        df_base,
        f_sku=f_sku,
        f_titulo=f_titulo,
        f_variante=f_variante,
        f_vendedor=f_vendedor,
        f_stock=f_stock,
        f_quiebre30=f_quiebre30,
        f_quiebre7=f_quiebre7,
    )
    st.session_state.inv_df_filtrado = filtrado.head(limite).copy()

if limpiar:
    st.session_state.inv_df_filtrado = df_base.head(limite).copy()
    st.rerun()

if st.session_state.inv_df_filtrado.empty:
    st.session_state.inv_df_filtrado = df_base.head(500).copy()

df = st.session_state.inv_df_filtrado.copy()


# =========================================================
# KPIs
# =========================================================
total_skus = df["sku"].nunique()
total_registros = len(df)
stock_total = df["stock_disponible"].sum()
stock_valorizado_total = df["stock_valorizado"].sum()
quiebres30 = (df["quiebre_stock_30_dias"] > 0).sum()
quiebres7 = (df["quiebre_stock_7_dias"] > 0).sum()

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("SKUs", fmt_int(total_skus))
k2.metric("Registros", fmt_int(total_registros))
k3.metric("Stock total", fmt_int(stock_total))
k4.metric("Stock valorizado", fmt_money(stock_valorizado_total))
k5.metric("Quiebres 30 días", fmt_int(quiebres30))
k6.metric("Quiebres 7 días", fmt_int(quiebres7))

st.markdown("---")


# =========================================================
# Tabla y exportación
# =========================================================
st.markdown("### Detalle de inventario")

col_info, col_export = st.columns([3, 1])
with col_info:
    st.caption(
        f"Mostrando {len(df)} registros. Campos base detectados: SKU, título, variante, stock disponible, costo fijo, stock valorizado y vendedor."
    )
with col_export:
    csv_bytes = build_export_csv(df)
    st.download_button(
        label="Exportar CSV",
        data=csv_bytes,
        file_name=f"informe_inventarios_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

df_show = df.copy()

money_cols = [
    "costo_fijo",
    "valor_venta_30_dias",
    "valor_venta_7_dias",
    "precio_venta_unitario",
    "stock_valorizado",
]
int_cols = [
    "stock_disponible",
    "und_vendidas_30_dias",
    "und_vendidas_7_dias",
    "quiebre_stock_30_dias",
    "quiebre_stock_7_dias",
]

for col in money_cols:
    if col in df_show.columns:
        df_show[col] = df_show[col].apply(fmt_money)

for col in int_cols:
    if col in df_show.columns:
        df_show[col] = df_show[col].apply(fmt_int)

column_order = [
    "sku",
    "titulo_ecom",
    "sku_variante",
    "vendedor",
    "stock_disponible",
    "costo_fijo",
    "stock_valorizado",
    "precio_venta_unitario",
    "valor_venta_30_dias",
    "und_vendidas_30_dias",
    "valor_venta_7_dias",
    "und_vendidas_7_dias",
    "quiebre_stock_30_dias",
    "quiebre_stock_7_dias",
]
column_order = [c for c in column_order if c in df_show.columns]
resto = [c for c in df_show.columns if c not in column_order]
df_show = df_show[column_order + resto]

st.dataframe(
    df_show,
    use_container_width=True,
    height=620,
    column_config={
        "sku": st.column_config.TextColumn("SKU", width="medium"),
        "titulo_ecom": st.column_config.TextColumn("Título", width="large"),
        "sku_variante": st.column_config.TextColumn("SKU variante", width="medium"),
        "vendedor": st.column_config.TextColumn("Vendedor", width="medium"),
        "stock_disponible": st.column_config.TextColumn("Stock disponible", width="small"),
        "costo_fijo": st.column_config.TextColumn("Costo fijo", width="small"),
        "stock_valorizado": st.column_config.TextColumn("Stock valorizado", width="small"),
        "precio_venta_unitario": st.column_config.TextColumn("Precio venta unitario", width="small"),
        "valor_venta_30_dias": st.column_config.TextColumn("Valor venta 30 días", width="small"),
        "und_vendidas_30_dias": st.column_config.TextColumn("Und vendidas 30 días", width="small"),
        "valor_venta_7_dias": st.column_config.TextColumn("Valor venta 7 días", width="small"),
        "und_vendidas_7_dias": st.column_config.TextColumn("Und vendidas 7 días", width="small"),
        "quiebre_stock_30_dias": st.column_config.TextColumn("Quiebre stock 30 días", width="small"),
        "quiebre_stock_7_dias": st.column_config.TextColumn("Quiebre stock 7 días", width="small"),
    },
)


# =========================================================
# Resúmenes
# =========================================================
st.markdown("---")
st.markdown("### Resumen por vendedor")

res_vendedor = (
    df.groupby("vendedor", dropna=False)
    .agg(
        registros=("sku", "count"),
        skus_unicos=("sku", "nunique"),
        stock_total=("stock_disponible", "sum"),
        stock_valorizado=("stock_valorizado", "sum"),
        valor_venta_30_dias=("valor_venta_30_dias", "sum"),
        valor_venta_7_dias=("valor_venta_7_dias", "sum"),
    )
    .reset_index()
    .sort_values("stock_valorizado", ascending=False)
)

res_vendedor_show = res_vendedor.copy()
for col in ["stock_total"]:
    res_vendedor_show[col] = res_vendedor_show[col].apply(fmt_int)
for col in ["stock_valorizado", "valor_venta_30_dias", "valor_venta_7_dias"]:
    res_vendedor_show[col] = res_vendedor_show[col].apply(fmt_money)

st.dataframe(res_vendedor_show, use_container_width=True, height=240)


st.markdown("### Top 20 por stock valorizado")

top_stock = (
    df.sort_values("stock_valorizado", ascending=False)
    .head(20)
    .copy()
)

top_stock_show = top_stock[
    [c for c in ["sku", "titulo_ecom", "sku_variante", "vendedor", "stock_disponible", "costo_fijo", "stock_valorizado"] if c in top_stock.columns]
].copy()

if "stock_disponible" in top_stock_show.columns:
    top_stock_show["stock_disponible"] = top_stock_show["stock_disponible"].apply(fmt_int)
if "costo_fijo" in top_stock_show.columns:
    top_stock_show["costo_fijo"] = top_stock_show["costo_fijo"].apply(fmt_money)
if "stock_valorizado" in top_stock_show.columns:
    top_stock_show["stock_valorizado"] = top_stock_show["stock_valorizado"].apply(fmt_money)

st.dataframe(top_stock_show, use_container_width=True, height=420)
