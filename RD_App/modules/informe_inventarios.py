import io

import pandas as pd
import streamlit as st

from services.db import fetch_all


st.title("Informe de Inventarios")
st.caption("Vista consolidada de stock, ventas, quiebre y valorización.")
st.markdown("---")


def fmt_money(v):
    try:
        return f"$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "-"


def fmt_int(v):
    try:
        return f"{int(round(float(v))):,}".replace(",", ".")
    except Exception:
        return "-"


def fmt_float(v, decimals=2):
    try:
        return f"{float(v):,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "-"


def safe_numeric(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


@st.cache_data(show_spinner=False)
def cargar_inventarios():
    rows = fetch_all("SELECT * FROM rd_tabla_inventarios")
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    expected_cols = [
        "sku",
        "titulo_ecom",
        "sku_variante",
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
        "vendedor",
    ]

    for col in expected_cols:
        if col not in df.columns:
            df[col] = pd.NA

    df = safe_numeric(
        df,
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

    for c in ["sku", "titulo_ecom", "sku_variante", "vendedor"]:
        df[c] = df[c].fillna("").astype(str)

    return df


def aplicar_filtros(df, f_sku, f_titulo, f_sku_variante, f_vendedores):
    vista = df.copy()

    if f_sku.strip():
        vista = vista[vista["sku"].str.contains(f_sku.strip(), case=False, na=False)]

    if f_titulo.strip():
        vista = vista[vista["titulo_ecom"].str.contains(f_titulo.strip(), case=False, na=False)]

    if f_sku_variante.strip():
        vista = vista[vista["sku_variante"].str.contains(f_sku_variante.strip(), case=False, na=False)]

    if f_vendedores:
        vista = vista[vista["vendedor"].isin(f_vendedores)]

    return vista


def build_export_df(df):
    return df.copy()


def to_csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8-sig")


def to_excel_bytes(df):
    output = io.BytesIO()

    engine = None
    try:
        import openpyxl  # noqa: F401
        engine = "openpyxl"
    except Exception:
        try:
            import xlsxwriter  # noqa: F401
            engine = "xlsxwriter"
        except Exception:
            return None

    with pd.ExcelWriter(output, engine=engine) as writer:
        df.to_excel(writer, index=False, sheet_name="inventarios")

    return output.getvalue()


df_base = cargar_inventarios()

if df_base.empty:
    st.warning("No se encontraron datos en rd_tabla_inventarios.")
    st.stop()

vendedores = sorted([v for v in df_base["vendedor"].dropna().unique().tolist() if str(v).strip()])

sugerencias_sku = sorted(df_base["sku"].dropna().astype(str).unique().tolist())
sugerencias_titulo = sorted(df_base["titulo_ecom"].dropna().astype(str).unique().tolist())
sugerencias_sku_variante = sorted(df_base["sku_variante"].dropna().astype(str).unique().tolist())

col1, col2, col3, col4 = st.columns(4)

with col1:
    f_sku = st.text_input("SKU")
    if f_sku:
        suger_sku = [x for x in sugerencias_sku if f_sku.lower() in x.lower()][:10]
        if suger_sku:
            st.caption("Sugerencias SKU: " + " | ".join(suger_sku))

with col2:
    f_titulo = st.text_input("Título ecom")
    if f_titulo:
        suger_titulo = [x for x in sugerencias_titulo if f_titulo.lower() in x.lower()][:10]
        if suger_titulo:
            st.caption("Sugerencias título: " + " | ".join(suger_titulo))

with col3:
    f_sku_variante = st.text_input("SKU variante")
    if f_sku_variante:
        suger_var = [x for x in sugerencias_sku_variante if f_sku_variante.lower() in x.lower()][:10]
        if suger_var:
            st.caption("Sugerencias variante: " + " | ".join(suger_var))

with col4:
    f_vendedores = st.multiselect("Vendedor", options=vendedores)

df_vista = aplicar_filtros(df_base, f_sku, f_titulo, f_sku_variante, f_vendedores)

col_dl1, col_dl2, _ = st.columns([1, 1, 2])
export_df = build_export_df(df_vista)
excel_bytes = to_excel_bytes(export_df)

with col_dl1:
    st.download_button(
        "Descargar CSV",
        data=to_csv_bytes(export_df),
        file_name="inventarios_filtrados.csv",
        mime="text/csv",
        use_container_width=True,
    )

with col_dl2:
    if excel_bytes is not None:
        st.download_button(
            "Descargar Excel",
            data=excel_bytes,
            file_name="inventarios_filtrados.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    else:
        st.button("Descargar Excel", disabled=True, use_container_width=True)
        st.caption("Excel no disponible en este entorno; usa CSV.")

st.markdown("---")

stock_disponible_total = df_vista["stock_disponible"].sum()
valor_7_total = df_vista["valor_venta_7_dias"].sum()
valor_30_total = df_vista["valor_venta_30_dias"].sum()
und_7_total = df_vista["und_vendidas_7_dias"].sum()
und_30_total = df_vista["und_vendidas_30_dias"].sum()
quiebre_7_prom = df_vista["quiebre_stock_7_dias"].mean() if not df_vista.empty else 0
quiebre_30_prom = df_vista["quiebre_stock_30_dias"].mean() if not df_vista.empty else 0
stock_valorizado_total = df_vista["stock_valorizado"].sum()

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.metric("Suma stock disponible", fmt_int(stock_disponible_total))
with k2:
    st.metric("Valor vendido 7 días", fmt_money(valor_7_total))
with k3:
    st.metric("Valor vendido 30 días", fmt_money(valor_30_total))
with k4:
    st.metric("Suma stock valorizado", fmt_money(stock_valorizado_total))

k5, k6, k7, k8 = st.columns(4)
with k5:
    st.metric("Und vendidas 7 días", fmt_int(und_7_total))
with k6:
    st.metric("Und vendidas 30 días", fmt_int(und_30_total))
with k7:
    st.metric("Prom. quiebre stock 7 días", fmt_float(quiebre_7_prom))
with k8:
    st.metric("Prom. quiebre stock 30 días", fmt_float(quiebre_30_prom))

st.markdown("---")
st.markdown(f"**{len(df_vista)} registros**")

df_show = df_vista.copy()

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
]

for c in money_cols:
    if c in df_show.columns:
        df_show[c] = df_show[c].apply(fmt_money)

for c in int_cols:
    if c in df_show.columns:
        df_show[c] = df_show[c].apply(fmt_int)

for c in ["quiebre_stock_30_dias", "quiebre_stock_7_dias"]:
    if c in df_show.columns:
        df_show[c] = df_show[c].apply(fmt_float)

column_order = [
    "sku",
    "titulo_ecom",
    "sku_variante",
    "vendedor",
    "costo_fijo",
    "stock_disponible",
    "valor_venta_7_dias",
    "valor_venta_30_dias",
    "und_vendidas_7_dias",
    "und_vendidas_30_dias",
    "quiebre_stock_7_dias",
    "quiebre_stock_30_dias",
    "precio_venta_unitario",
    "stock_valorizado",
]

column_order = [c for c in column_order if c in df_show.columns]
df_show = df_show[column_order]

st.dataframe(
    df_show,
    use_container_width=True,
    height=600,
    column_config={
        "sku": st.column_config.TextColumn("SKU", width="medium"),
        "titulo_ecom": st.column_config.TextColumn("Título ecom", width="large"),
        "sku_variante": st.column_config.TextColumn("SKU variante", width="medium"),
        "vendedor": st.column_config.TextColumn("Vendedor", width="medium"),
    },
)
