import io
import pandas as pd
import streamlit as st

from services.db import fetch_all

st.title("Informe de Inventarios")
st.caption("Consulta de stock, ventas y quiebres desde la tabla informada en Postgres.")
st.markdown("---")


# =========================
# Config
# =========================
TABLA_INVENTARIOS = "tabla_informada"


# =========================
# Helpers
# =========================
def to_num(x):
    if pd.isna(x):
        return 0.0
    if isinstance(x, (int, float)):
        return float(x)

    s = str(x).strip()
    if s == "":
        return 0.0

    s = s.replace("$", "").replace(" ", "")

    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")

    try:
        return float(s)
    except Exception:
        return 0.0


def fmt_money(x):
    try:
        return f"$ {float(x):,.0f}".replace(",", ".")
    except Exception:
        return "$ 0"


def fmt_int(x):
    try:
        return f"{int(round(float(x))):,}".replace(",", ".")
    except Exception:
        return "0"


def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    rename_map = {
        "titulo_ecom": "tituloecom",
        "sku_variante": "skuvariante",
        "costo_fijo": "costofijo",
        "stock_disponible": "stockdisponible",
        "valor_venta_30_dias": "valorventa30dias",
        "und_vendidas_30_dias": "undvendidas30dias",
        "valor_venta_7_dias": "valorventa7dias",
        "und_vendidas_7_dias": "undvendidas7dias",
        "quiebre_stock_30_dias": "quiebrestock30dias",
        "quiebre_stock_7_dias": "quiebrestock7dias",
        "precio_venta_unitario": "precioventaunitario",
        "stock_valorizado": "stockvalorizado",
    }
    df = df.rename(columns=rename_map)

    esperadas = [
        "sku",
        "tituloecom",
        "skuvariante",
        "costofijo",
        "stockdisponible",
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

    for col in esperadas:
        if col not in df.columns:
            df[col] = "" if col in ["sku", "tituloecom", "skuvariante", "vendedor"] else 0

    numericas = [
        "costofijo",
        "stockdisponible",
        "valorventa30dias",
        "undvendidas30dias",
        "valorventa7dias",
        "undvendidas7dias",
        "quiebrestock30dias",
        "quiebrestock7dias",
        "precioventaunitario",
        "stockvalorizado",
    ]

    for col in numericas:
        df[col] = df[col].apply(to_num)

    df["sku"] = df["sku"].astype(str).str.strip()
    df["tituloecom"] = df["tituloecom"].astype(str).str.strip()
    df["skuvariante"] = df["skuvariante"].astype(str).str.strip()
    df["vendedor"] = df["vendedor"].astype(str).str.strip()

    return df


def aplicar_filtros(df, vendedor, sku_texto, titulo_texto, solo_con_stock):
    vista = df.copy()

    if vendedor != "Todos":
        vista = vista[vista["vendedor"] == vendedor]

    if sku_texto.strip():
        patron = sku_texto.strip()
        vista = vista[
            vista["sku"].astype(str).str.contains(patron, case=False, na=False)
            | vista["skuvariante"].astype(str).str.contains(patron, case=False, na=False)
        ]

    if titulo_texto.strip():
        patron = titulo_texto.strip()
        vista = vista[vista["tituloecom"].astype(str).str.contains(patron, case=False, na=False)]

    if solo_con_stock:
        vista = vista[vista["stockdisponible"] > 0]

    return vista


def preparar_tabla(df):
    vista = df.copy()

    vista["cobertura_dias_30"] = vista.apply(
        lambda r: (r["stockdisponible"] / (r["undvendidas30dias"] / 30)) if r["undvendidas30dias"] > 0 else 9999,
        axis=1,
    )
    vista["cobertura_dias_7"] = vista.apply(
        lambda r: (r["stockdisponible"] / (r["undvendidas7dias"] / 7)) if r["undvendidas7dias"] > 0 else 9999,
        axis=1,
    )
    vista["rotacion_30"] = vista.apply(
        lambda r: (r["undvendidas30dias"] / r["stockdisponible"] * 100) if r["stockdisponible"] > 0 else 0,
        axis=1,
    )

    vista["stockdisponible"] = vista["stockdisponible"].round(0)
    vista["undvendidas30dias"] = vista["undvendidas30dias"].round(0)
    vista["undvendidas7dias"] = vista["undvendidas7dias"].round(0)
    vista["quiebrestock30dias"] = vista["quiebrestock30dias"].round(0)
    vista["quiebrestock7dias"] = vista["quiebrestock7dias"].round(0)
    vista["costofijo"] = vista["costofijo"].round(2)
    vista["valorventa30dias"] = vista["valorventa30dias"].round(2)
    vista["valorventa7dias"] = vista["valorventa7dias"].round(2)
    vista["precioventaunitario"] = vista["precioventaunitario"].round(2)
    vista["stockvalorizado"] = vista["stockvalorizado"].round(2)
    vista["cobertura_dias_30"] = vista["cobertura_dias_30"].replace([float("inf")], 9999).round(1)
    vista["cobertura_dias_7"] = vista["cobertura_dias_7"].replace([float("inf")], 9999).round(1)
    vista["rotacion_30"] = vista["rotacion_30"].round(1)

    return vista


def exportar_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="inventarios")
    return output.getvalue()


# =========================
# Carga desde SQL
# =========================
try:
    resultados = fetch_all(f"SELECT * FROM {TABLA_INVENTARIOS}")
except Exception as e:
    st.error(f"No se pudo consultar la tabla {TABLA_INVENTARIOS}: {e}")
    st.stop()

if not resultados:
    st.warning(f"La tabla {TABLA_INVENTARIOS} no devolvió registros.")
    st.stop()

df = pd.DataFrame(resultados)
df = normalizar_columnas(df)

st.success(f"Datos cargados desde SQL: {len(df)} registros")

# =========================
# Filtros
# =========================
st.markdown("### Filtros")

col1, col2, col3, col4 = st.columns(4)

vendedores = sorted([x for x in df["vendedor"].dropna().unique().tolist() if str(x).strip()])

with col1:
    filtro_vendedor = st.selectbox("Vendedor", ["Todos"] + vendedores)
with col2:
    filtro_sku = st.text_input("SKU / Variante")
with col3:
    filtro_titulo = st.text_input("Título")
with col4:
    solo_con_stock = st.checkbox("Solo con stock", value=False)

df_filtrado = aplicar_filtros(
    df,
    filtro_vendedor,
    filtro_sku,
    filtro_titulo,
    solo_con_stock,
)

df_filtrado = preparar_tabla(df_filtrado)

# =========================
# KPIs
# =========================
total_skus = df_filtrado["skuvariante"].nunique() if "skuvariante" in df_filtrado.columns else len(df_filtrado)
stock_total = df_filtrado["stockdisponible"].sum()
stock_valorizado = df_filtrado["stockvalorizado"].sum()
valor_30 = df_filtrado["valorventa30dias"].sum()
valor_7 = df_filtrado["valorventa7dias"].sum()
und_30 = df_filtrado["undvendidas30dias"].sum()
und_7 = df_filtrado["undvendidas7dias"].sum()
quiebre_30 = df_filtrado["quiebrestock30dias"].sum()
quiebre_7 = df_filtrado["quiebrestock7dias"].sum()

col_a, col_b, col_c, col_d = st.columns(4)
col_a.metric("SKU variantes", fmt_int(total_skus))
col_b.metric("Stock disponible", fmt_int(stock_total))
col_c.metric("Stock valorizado", fmt_money(stock_valorizado))
col_d.metric("Venta 30 días", fmt_money(valor_30))

col_e, col_f, col_g, col_h = st.columns(4)
col_e.metric("Venta 7 días", fmt_money(valor_7))
col_f.metric("Unidades 30 días", fmt_int(und_30))
col_g.metric("Unidades 7 días", fmt_int(und_7))
col_h.metric("Quiebres 30 días", fmt_int(quiebre_30))

st.markdown("---")

# =========================
# Rankings
# =========================
col_r1, col_r2 = st.columns(2)

with col_r1:
    st.markdown("### Top 10 por venta 30 días")
    top_venta = (
        df_filtrado.sort_values("valorventa30dias", ascending=False)[
            ["skuvariante", "tituloecom", "vendedor", "valorventa30dias", "undvendidas30dias", "stockdisponible"]
        ]
        .head(10)
        .copy()
    )
    top_venta["valorventa30dias"] = top_venta["valorventa30dias"].apply(fmt_money)
    top_venta["undvendidas30dias"] = top_venta["undvendidas30dias"].apply(fmt_int)
    top_venta["stockdisponible"] = top_venta["stockdisponible"].apply(fmt_int)
    st.dataframe(top_venta, use_container_width=True, hide_index=True)

with col_r2:
    st.markdown("### Top 10 quiebres 30 días")
    top_quiebres = (
        df_filtrado.sort_values("quiebrestock30dias", ascending=False)[
            ["skuvariante", "tituloecom", "vendedor", "quiebrestock30dias", "undvendidas30dias", "stockdisponible"]
        ]
        .head(10)
        .copy()
    )
    top_quiebres["quiebrestock30dias"] = top_quiebres["quiebrestock30dias"].apply(fmt_int)
    top_quiebres["undvendidas30dias"] = top_quiebres["undvendidas30dias"].apply(fmt_int)
    top_quiebres["stockdisponible"] = top_quiebres["stockdisponible"].apply(fmt_int)
    st.dataframe(top_quiebres, use_container_width=True, hide_index=True)

st.markdown("---")

# =========================
# Alertas
# =========================
st.markdown("### Alertas de cobertura")

alertas = df_filtrado[
    (
        (df_filtrado["undvendidas30dias"] > 0) &
        (df_filtrado["cobertura_dias_30"] <= 15)
    )
    |
    (
        (df_filtrado["stockdisponible"] <= 0) &
        (df_filtrado["undvendidas30dias"] > 0)
    )
].copy()

alertas = alertas.sort_values(["cobertura_dias_30", "valorventa30dias"], ascending=[True, False])

if alertas.empty:
    st.success("No hay alertas críticas con los filtros actuales.")
else:
    alertas_show = alertas[
        [
            "skuvariante",
            "tituloecom",
            "vendedor",
            "stockdisponible",
            "undvendidas30dias",
            "valorventa30dias",
            "quiebrestock30dias",
            "cobertura_dias_30",
        ]
    ].copy()

    alertas_show["stockdisponible"] = alertas_show["stockdisponible"].apply(fmt_int)
    alertas_show["undvendidas30dias"] = alertas_show["undvendidas30dias"].apply(fmt_int)
    alertas_show["valorventa30dias"] = alertas_show["valorventa30dias"].apply(fmt_money)
    alertas_show["quiebrestock30dias"] = alertas_show["quiebrestock30dias"].apply(fmt_int)

    st.dataframe(alertas_show, use_container_width=True, hide_index=True)

st.markdown("---")

# =========================
# Tabla principal
# =========================
st.markdown(f"### Detalle ({len(df_filtrado)} filas)")

tabla = df_filtrado[
    [
        "sku",
        "tituloecom",
        "skuvariante",
        "vendedor",
        "costofijo",
        "precioventaunitario",
        "stockdisponible",
        "stockvalorizado",
        "valorventa30dias",
        "undvendidas30dias",
        "valorventa7dias",
        "undvendidas7dias",
        "quiebrestock30dias",
        "quiebrestock7dias",
        "cobertura_dias_30",
        "cobertura_dias_7",
        "rotacion_30",
    ]
].copy()

st.dataframe(
    tabla,
    use_container_width=True,
    hide_index=True,
    height=520,
    column_config={
        "sku": st.column_config.TextColumn("SKU", width="medium"),
        "tituloecom": st.column_config.TextColumn("Título", width="large"),
        "skuvariante": st.column_config.TextColumn("SKU variante", width="medium"),
        "vendedor": st.column_config.TextColumn("Vendedor", width="medium"),
        "costofijo": st.column_config.NumberColumn("Costo fijo", format="$ %.2f"),
        "precioventaunitario": st.column_config.NumberColumn("Precio venta", format="$ %.2f"),
        "stockdisponible": st.column_config.NumberColumn("Stock", format="%.0f"),
        "stockvalorizado": st.column_config.NumberColumn("Stock valorizado", format="$ %.2f"),
        "valorventa30dias": st.column_config.NumberColumn("Venta 30d", format="$ %.2f"),
        "undvendidas30dias": st.column_config.NumberColumn("Und 30d", format="%.0f"),
        "valorventa7dias": st.column_config.NumberColumn("Venta 7d", format="$ %.2f"),
        "undvendidas7dias": st.column_config.NumberColumn("Und 7d", format="%.0f"),
        "quiebrestock30dias": st.column_config.NumberColumn("Quiebres 30d", format="%.0f"),
        "quiebrestock7dias": st.column_config.NumberColumn("Quiebres 7d", format="%.0f"),
        "cobertura_dias_30": st.column_config.NumberColumn("Cobertura 30d", format="%.1f"),
        "cobertura_dias_7": st.column_config.NumberColumn("Cobertura 7d", format="%.1f"),
        "rotacion_30": st.column_config.NumberColumn("Rotación 30d %", format="%.1f"),
    },
)

excel_bytes = exportar_excel(tabla)

st.download_button(
    "Descargar Excel",
    data=excel_bytes,
    file_name="informe_inventarios.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)
