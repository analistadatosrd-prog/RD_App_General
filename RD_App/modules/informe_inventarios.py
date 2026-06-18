# modules/informe_inventarios.py

import pandas as pd
import streamlit as st

from services.db import fetch_all

st.title("Informe de Inventarios")
st.caption("Vista consolidada de stock, ventas, valorización y quiebres por SKU.")
st.markdown("---")


for key, default in [
    ("inv_base", pd.DataFrame()),
    ("inv_filtrado", pd.DataFrame()),
]:
    if key not in st.session_state:
        st.session_state[key] = default


def fmt_money(valor):
    try:
        return f"$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "-"


def fmt_int(valor):
    try:
        return f"{int(round(float(valor), 0)):,}".replace(",", ".")
    except Exception:
        return "-"


def normalizar_inventario(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    renames = {
        "titulo_ecom": "tituloecom",
        "titulo": "tituloecom",
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
    df.rename(columns={k: v for k, v in renames.items() if k in df.columns}, inplace=True)

    numeric_cols = [
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

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if "dias_cobertura_30" not in df.columns:
        if {"stockdisponible", "undvendidas30dias"}.issubset(df.columns):
            df["dias_cobertura_30"] = df.apply(
                lambda r: round(r["stockdisponible"] / (r["undvendidas30dias"] / 30), 1)
                if r["undvendidas30dias"] > 0 else None,
                axis=1
            )

    if "dias_cobertura_7" not in df.columns:
        if {"stockdisponible", "undvendidas7dias"}.issubset(df.columns):
            df["dias_cobertura_7"] = df.apply(
                lambda r: round(r["stockdisponible"] / (r["undvendidas7dias"] / 7), 1)
                if r["undvendidas7dias"] > 0 else None,
                axis=1
            )

    if "rotacion_30" not in df.columns:
        if {"undvendidas30dias", "stockdisponible"}.issubset(df.columns):
            df["rotacion_30"] = df.apply(
                lambda r: round(r["undvendidas30dias"] / r["stockdisponible"], 2)
                if r["stockdisponible"] > 0 else None,
                axis=1
            )

    if "rotacion_7" not in df.columns:
        if {"undvendidas7dias", "stockdisponible"}.issubset(df.columns):
            df["rotacion_7"] = df.apply(
                lambda r: round(r["undvendidas7dias"] / r["stockdisponible"], 2)
                if r["stockdisponible"] > 0 else None,
                axis=1
            )

    if "estado_stock" not in df.columns and "stockdisponible" in df.columns:
        def clasificar_stock(x):
            if pd.isna(x):
                return "Sin dato"
            if x < 0:
                return "Stock negativo"
            if x == 0:
                return "Sin stock"
            if x <= 5:
                return "Stock bajo"
            return "Con stock"
        df["estado_stock"] = df["stockdisponible"].apply(clasificar_stock)

    return df


def apply_filtros(
    df: pd.DataFrame,
    f_vendedor,
    f_sku,
    f_titulo,
    f_variante,
    f_estado_stock,
    f_stock_desde,
    f_stock_hasta,
    f_solo_quiebre_30,
    f_solo_quiebre_7,
):
    if df.empty:
        return df

    vista = df.copy()

    if f_vendedor != "Todos" and "vendedor" in vista.columns:
        vista = vista[vista["vendedor"] == f_vendedor]

    if f_sku.strip() and "sku" in vista.columns:
        vista = vista[vista["sku"].astype(str).str.contains(f_sku.strip(), case=False, na=False)]

    if f_titulo.strip() and "tituloecom" in vista.columns:
        vista = vista[vista["tituloecom"].astype(str).str.contains(f_titulo.strip(), case=False, na=False)]

    if f_variante.strip() and "variante" in vista.columns:
        vista = vista[vista["variante"].astype(str).str.contains(f_variante.strip(), case=False, na=False)]

    if f_estado_stock != "Todos" and "estado_stock" in vista.columns:
        vista = vista[vista["estado_stock"] == f_estado_stock]

    if "stockdisponible" in vista.columns:
        vista = vista[vista["stockdisponible"] >= f_stock_desde]
        if f_stock_hasta is not None:
            vista = vista[vista["stockdisponible"] <= f_stock_hasta]

    if f_solo_quiebre_30 and "quiebrestock30dias" in vista.columns:
        vista = vista[vista["quiebrestock30dias"] > 0]

    if f_solo_quiebre_7 and "quiebrestock7dias" in vista.columns:
        vista = vista[vista["quiebrestock7dias"] > 0]

    return vista


def mostrar_metricas(df: pd.DataFrame):
    if df.empty:
        st.info("No hay datos para mostrar.")
        return

    total_skus = len(df)
    stock_total = float(df["stockdisponible"].sum()) if "stockdisponible" in df.columns else 0
    stock_valorizado = float(df["stockvalorizado"].sum()) if "stockvalorizado" in df.columns else 0
    venta_30 = float(df["valorventa30dias"].sum()) if "valorventa30dias" in df.columns else 0
    venta_7 = float(df["valorventa7dias"].sum()) if "valorventa7dias" in df.columns else 0
    quiebres_30 = int((df["quiebrestock30dias"] > 0).sum()) if "quiebrestock30dias" in df.columns else 0
    quiebres_7 = int((df["quiebrestock7dias"] > 0).sum()) if "quiebrestock7dias" in df.columns else 0

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("SKUs", fmt_int(total_skus))
    c2.metric("Stock total", fmt_int(stock_total))
    c3.metric("Stock valorizado", fmt_money(stock_valorizado))
    c4.metric("Venta 30 días", fmt_money(venta_30))
    c5.metric("Quiebres 30 días", fmt_int(quiebres_30))
    c6.metric("Quiebres 7 días", fmt_int(quiebres_7))

    c7, c8 = st.columns(2)
    with c7:
        st.metric("Venta 7 días", fmt_money(venta_7))
    with c8:
        cobertura_media = df["dias_cobertura_30"].dropna().mean() if "dias_cobertura_30" in df.columns else None
        st.metric("Cobertura media 30 días", "-" if pd.isna(cobertura_media) else f"{cobertura_media:.1f} días")


if not st.session_state.get("authenticated"):
    st.error("No hay una sesión autenticada.")
    st.stop()


if st.session_state.inv_base.empty:
    resultados = fetch_all("SELECT * FROM informe_inventarios")
    if not resultados:
        resultados = fetch_all("SELECT * FROM rd_informe_inventarios")
    if not resultados:
        resultados = fetch_all("SELECT * FROM rd_tabla_inventarios")

    if resultados:
        df_base = pd.DataFrame(resultados)
        df_base = normalizar_inventario(df_base)
        st.session_state.inv_base = df_base.copy()
        st.session_state.inv_filtrado = df_base.copy()
    else:
        st.session_state.inv_base = pd.DataFrame()
        st.session_state.inv_filtrado = pd.DataFrame()


if st.session_state.inv_base.empty:
    st.warning("No se encontraron datos de inventario en las tablas esperadas.")
    st.stop()


df_base = st.session_state.inv_base.copy()

vendedores = sorted(df_base["vendedor"].dropna().astype(str).unique().tolist()) if "vendedor" in df_base.columns else []
estados_stock = sorted(df_base["estado_stock"].dropna().astype(str).unique().tolist()) if "estado_stock" in df_base.columns else []

st.markdown("### Filtros")

col1, col2, col3, col4 = st.columns(4)
with col1:
    f_vendedor = st.selectbox("Vendedor", ["Todos"] + vendedores)
    f_sku = st.text_input("SKU")
with col2:
    f_titulo = st.text_input("Título")
    f_variante = st.text_input("Variante")
with col3:
    f_estado_stock = st.selectbox("Estado stock", ["Todos"] + estados_stock)
    f_stock_desde = st.number_input("Stock mínimo", value=0.0, step=1.0)
with col4:
    f_stock_hasta_val = st.text_input("Stock máximo", value="")
    f_solo_quiebre_30 = st.checkbox("Solo con quiebre 30 días")
    f_solo_quiebre_7 = st.checkbox("Solo con quiebre 7 días")

colf1, colf2 = st.columns([1, 2])
with colf1:
    btn_filtrar = st.button("Aplicar filtros", use_container_width=True)
with colf2:
    orden = st.selectbox(
        "Ordenar por",
        [
            "stockvalorizado",
            "valorventa30dias",
            "valorventa7dias",
            "stockdisponible",
            "undvendidas30dias",
            "undvendidas7dias",
            "quiebrestock30dias",
            "quiebrestock7dias",
        ],
        index=0,
    )

desc = st.toggle("Orden descendente", value=True)

f_stock_hasta = None
if str(f_stock_hasta_val).strip():
    try:
        f_stock_hasta = float(f_stock_hasta_val)
    except Exception:
        st.warning("Stock máximo inválido. Se ignorará ese filtro.")


if btn_filtrar:
    df_filtrado = apply_filtros(
        df_base,
        f_vendedor,
        f_sku,
        f_titulo,
        f_variante,
        f_estado_stock,
        f_stock_desde,
        f_stock_hasta,
        f_solo_quiebre_30,
        f_solo_quiebre_7,
    )

    if orden in df_filtrado.columns:
        df_filtrado = df_filtrado.sort_values(by=orden, ascending=not desc, na_position="last")

    st.session_state.inv_filtrado = df_filtrado.copy()


df_vista = st.session_state.inv_filtrado.copy()

mostrar_metricas(df_vista)
st.markdown("---")
st.markdown(f"**{len(df_vista)} registros en la vista**")

df_show = df_vista.copy()

money_cols = [
    "costofijo",
    "valorventa30dias",
    "valorventa7dias",
    "precioventaunitario",
    "stockvalorizado",
]
int_like_cols = [
    "stockdisponible",
    "undvendidas30dias",
    "undvendidas7dias",
    "quiebrestock30dias",
    "quiebrestock7dias",
]

for col in money_cols:
    if col in df_show.columns:
        df_show[col] = df_show[col].apply(fmt_money)

for col in int_like_cols:
    if col in df_show.columns:
        df_show[col] = df_show[col].apply(fmt_int)

if "dias_cobertura_30" in df_show.columns:
    df_show["dias_cobertura_30"] = df_show["dias_cobertura_30"].apply(
        lambda x: "-" if pd.isna(x) else f"{float(x):.1f}"
    )

if "dias_cobertura_7" in df_show.columns:
    df_show["dias_cobertura_7"] = df_show["dias_cobertura_7"].apply(
        lambda x: "-" if pd.isna(x) else f"{float(x):.1f}"
    )

if "rotacion_30" in df_show.columns:
    df_show["rotacion_30"] = df_show["rotacion_30"].apply(
        lambda x: "-" if pd.isna(x) else f"{float(x):.2f}"
    )

if "rotacion_7" in df_show.columns:
    df_show["rotacion_7"] = df_show["rotacion_7"].apply(
        lambda x: "-" if pd.isna(x) else f"{float(x):.2f}"
    )

columnas_preferidas = [
    "vendedor",
    "tituloecom",
    "sku",
    "variante",
    "estado_stock",
    "stockdisponible",
    "costofijo",
    "precioventaunitario",
    "stockvalorizado",
    "valorventa30dias",
    "undvendidas30dias",
    "valorventa7dias",
    "undvendidas7dias",
    "quiebrestock30dias",
    "quiebrestock7dias",
    "dias_cobertura_30",
    "dias_cobertura_7",
    "rotacion_30",
    "rotacion_7",
]

columnas_finales = [c for c in columnas_preferidas if c in df_show.columns] + [
    c for c in df_show.columns if c not in columnas_preferidas
]

st.dataframe(
    df_show[columnas_finales],
    use_container_width=True,
    height=650,
)

st.markdown("---")

csv_export = df_vista.to_csv(index=False).encode("utf-8")
st.download_button(
    "Descargar CSV filtrado",
    data=csv_export,
    file_name="informe_inventarios_filtrado.csv",
    mime="text/csv",
    use_container_width=True,
)
