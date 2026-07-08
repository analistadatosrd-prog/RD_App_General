import io
import pandas as pd
import streamlit as st

from services.db import fetch_all

st.set_page_config(
    page_title="Informe de inventarios",
    page_icon="📦",
    layout="wide"
)

st.markdown("""
<style>
.block-container {
    padding-top: 0.9rem;
    padding-bottom: 2rem;
    max-width: 96%;
}

div[data-testid="stAppViewContainer"] > .main .block-container {
    padding-top: 0.9rem !important;
}

h1 {
    margin-bottom: 0.8rem !important;
}

.inv-card {
    background: linear-gradient(135deg, #0f1b31 0%, #1a2b47 100%);
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 18px;
    padding: 18px 18px 16px 18px;
    box-shadow: 0 10px 28px rgba(0,0,0,.18);
    min-height: 126px;
    height: 100%;
}

.inv-card-title {
    font-size: 0.92rem;
    color: #cbd5e1;
    margin-bottom: 12px;
    font-weight: 600;
}

.inv-card-value {
    font-size: 1.95rem;
    font-weight: 800;
    color: #ffffff;
    line-height: 1.08;
    margin-bottom: 10px;
}

.inv-card-sub {
    margin-top: 0;
    font-size: 0.9rem;
    color: #94a3b8;
}

.filter-box {
    background: linear-gradient(180deg, #081120 0%, #0b1424 100%);
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 18px;
    padding: 22px 20px 18px 20px;
    margin-top: 18px;
    margin-bottom: 24px;
    box-shadow: 0 10px 30px rgba(0,0,0,.14);
}

.filter-box .stTextInput,
.filter-box .stSelectbox {
    margin-bottom: 0 !important;
}

.filter-actions {
    margin-top: 18px;
}

.visual-btn,
.visual-btn .stButton,
.visual-btn .stDownloadButton {
    width: 100%;
}

.visual-btn .stButton > button,
.visual-btn .stDownloadButton > button {
    width: 100%;
    min-height: 50px;
    height: 50px;
    border-radius: 14px;
    border: 1px solid rgba(255,255,255,.10);
    color: white;
    font-weight: 700;
    font-size: 0.95rem;
    padding: 0 18px;
    margin-top: 0 !important;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    white-space: nowrap;
}

.visual-btn .stButton > button {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
    box-shadow: 0 10px 20px rgba(37,99,235,.22);
}

.visual-btn.secondary .stButton > button {
    background: linear-gradient(135deg, #334155 0%, #1e293b 100%);
    box-shadow: 0 10px 20px rgba(15,23,42,.22);
}

.visual-btn.export .stDownloadButton > button {
    background: linear-gradient(135deg, #059669 0%, #047857 100%);
    box-shadow: 0 10px 20px rgba(5,150,105,.22);
}

.visual-btn .stButton > button:hover,
.visual-btn .stDownloadButton > button:hover {
    transform: translateY(-1px);
    border-color: rgba(255,255,255,.18);
}

div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div {
    min-height: 50px;
    border-radius: 14px !important;
    background: rgba(255,255,255,.03) !important;
}

label[data-testid="stWidgetLabel"] p {
    font-size: 0.88rem !important;
    font-weight: 600 !important;
    color: #dbe4f0 !important;
}

.status-chip {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    border-radius: 999px;
    padding: 8px 12px;
    font-weight: 700;
    font-size: .9rem;
}

.status-red {
    background: rgba(239,68,68,.16);
    color: #fecaca;
    border: 1px solid rgba(239,68,68,.28);
}

.status-yellow {
    background: rgba(245,158,11,.16);
    color: #fde68a;
    border: 1px solid rgba(245,158,11,.28);
}

.status-green {
    background: rgba(34,197,94,.16);
    color: #bbf7d0;
    border: 1px solid rgba(34,197,94,.28);
}

.section-title {
    font-size: 1.08rem;
    font-weight: 800;
    margin: 0 0 1rem 0;
    color: #f8fafc;
}

.source-text {
    font-size: .92rem;
    color: #94a3b8;
    margin-top: -2px;
    margin-bottom: 18px;
}

.kpi-row-gap {
    margin-top: 14px;
}

div[data-testid="stHorizontalBlock"] {
    gap: 1rem !important;
}
</style>
""", unsafe_allow_html=True)

st.title("Informe de inventarios")

for key, default in [
    ("inv_base", pd.DataFrame()),
    ("inv_filtrado", pd.DataFrame()),
    ("inv_source_table", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


def fmt_money(value):
    try:
        return f"$ {float(value):,.0f}".replace(",", ".")
    except Exception:
        return "$ 0"


def fmt_number(value, decimals=0):
    try:
        if decimals == 0:
            return f"{float(value):,.0f}".replace(",", ".")
        return f"{float(value):,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0"


def find_col(df, candidates):
    cols_lower = {c.lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in cols_lower:
            return cols_lower[candidate.lower()]
    return None


def to_numeric_safe(series):
    return pd.to_numeric(series, errors="coerce").fillna(0)


def build_quiebre_status(valor):
    if valor < 30:
        return "⚠️ Quiebre próximo", "status-red"
    elif valor <= 60:
        return "🟡 Estable", "status-yellow"
    return "✅ Quiebre alto", "status-green"


def render_card(title, value, subtext=""):
    st.markdown(
        f"""
        <div class="inv-card">
            <div class="inv-card-title">{title}</div>
            <div class="inv-card-value">{value}</div>
            <div class="inv-card-sub">{subtext}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_status_card(title, promedio_quiebre):
    texto, clase = build_quiebre_status(promedio_quiebre)
    st.markdown(
        f"""
        <div class="inv-card">
            <div class="inv-card-title">{title}</div>
            <div class="inv-card-value">{fmt_number(promedio_quiebre, 1)} días</div>
            <div class="inv-card-sub">
                <span class="status-chip {clase}">{texto}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def cargar_datos():
    tablas_candidatas = [
        "rd_tabla_inventarios",
        "informe_inventarios",
    ]

    errores = []

    for tabla in tablas_candidatas:
        try:
            rows = fetch_all(f"SELECT * FROM {tabla}")
            if rows:
                df = pd.DataFrame(rows)
                return df, tabla
        except Exception as e:
            errores.append(f"{tabla}: {type(e).__name__}")
            continue

    return pd.DataFrame(), None


if not st.session_state.get("authenticated"):
    st.error("No hay una sesión autenticada.")
    st.stop()

if st.session_state.inv_base.empty:
    df_cargado, tabla_origen = cargar_datos()

    if not df_cargado.empty:
        st.session_state.inv_base = df_cargado.copy()
        st.session_state.inv_filtrado = df_cargado.copy()
        st.session_state.inv_source_table = tabla_origen
    else:
        st.error("No se pudieron cargar datos de inventario desde PostgreSQL.")
        st.stop()

tabla_mostrada = st.session_state.get("inv_source_table") or "rd_tabla_inventarios"
st.markdown(
    f'<div class="source-text">Fuente: PostgreSQL | tabla {tabla_mostrada}</div>',
    unsafe_allow_html=True
)

df_base = st.session_state.inv_base.copy()

col_cuenta = find_col(df_base, ["cuenta"])
col_sku = find_col(df_base, ["sku"])
col_titulo = find_col(df_base, ["titulo", "titulo_ecom", "tituloecom"])
col_sku_variante = find_col(df_base, ["sku_variante", "skuvariante"])

col_stock = find_col(df_base, ["stock_disponible", "stockdisponible"])
col_costo = find_col(df_base, ["costo_fijo", "costofijo"])
col_stock_valorizado = find_col(df_base, ["stock_valorizado", "stockvalorizado"])

col_valor_venta_7 = find_col(df_base, ["valor_venta_7_dias", "valorventa7dias"])
col_und_7 = find_col(df_base, ["und_vendidas_7_dias", "undvendidas7dias"])
col_quiebre_7 = find_col(df_base, ["quiebre_stock_7_dias", "quiebrestock7dias"])

col_valor_venta_30 = find_col(df_base, ["valor_venta_30_dias", "valorventa30dias"])
col_und_30 = find_col(df_base, ["und_vendidas_30_dias", "undvendidas30dias"])
col_quiebre_30 = find_col(df_base, ["quiebre_stock_30_dias", "quiebrestock30dias"])

df_vista = st.session_state.inv_filtrado.copy()

stock_total = to_numeric_safe(df_vista[col_stock]).sum() if col_stock else 0
costo_stock = (to_numeric_safe(df_vista[col_stock]) * to_numeric_safe(df_vista[col_costo])).sum() if col_stock and col_costo else 0
stock_valorizado = to_numeric_safe(df_vista[col_stock_valorizado]).sum() if col_stock_valorizado else 0

valor_vendido_7 = to_numeric_safe(df_vista[col_valor_venta_7]).sum() if col_valor_venta_7 else 0
und_vendidas_7 = to_numeric_safe(df_vista[col_und_7]).sum() if col_und_7 else 0
prom_dia_7 = und_vendidas_7 / 7 if und_vendidas_7 else 0
quiebre_7_prom = to_numeric_safe(df_vista[col_quiebre_7]).mean() if col_quiebre_7 and len(df_vista) > 0 else 0

valor_vendido_30 = to_numeric_safe(df_vista[col_valor_venta_30]).sum() if col_valor_venta_30 else 0
und_vendidas_30 = to_numeric_safe(df_vista[col_und_30]).sum() if col_und_30 else 0
prom_dia_30 = und_vendidas_30 / 30 if und_vendidas_30 else 0
quiebre_30_prom = to_numeric_safe(df_vista[col_quiebre_30]).mean() if col_quiebre_30 and len(df_vista) > 0 else 0

st.markdown('<div class="section-title">Resumen visual</div>', unsafe_allow_html=True)

r1c1, r1c2, r1c3 = st.columns(3)
with r1c1:
    render_card("Stock total", fmt_number(stock_total), "Suma del stock")
with r1c2:
    render_card("Costo stock", fmt_money(costo_stock), "Suma de stock * costo_fijo")
with r1c3:
    render_card("Stock valorizado", fmt_money(stock_valorizado), "Suma de stock valorizado")

st.markdown('<div class="kpi-row-gap"></div>', unsafe_allow_html=True)

r2c1, r2c2, r2c3, r2c4 = st.columns(4)
with r2c1:
    render_card("Valor vendido 7 días", fmt_money(valor_vendido_7), "Total valor vendido últimos 7 días")
with r2c2:
    render_card("Und vendidas 7 días", fmt_number(und_vendidas_7), "Suma de unidades vendidas")
with r2c3:
    render_card("Prom ventas * día 7", fmt_number(prom_dia_7, 2), "und vendidas 7 días / 7")
with r2c4:
    render_status_card("Quiebre stock 7 días", quiebre_7_prom)

st.markdown('<div class="kpi-row-gap"></div>', unsafe_allow_html=True)

r3c1, r3c2, r3c3, r3c4 = st.columns(4)
with r3c1:
    render_card("Valor vendido 30 días", fmt_money(valor_vendido_30), "Total valor vendido últimos 30 días")
with r3c2:
    render_card("Und vendidas 30 días", fmt_number(und_vendidas_30), "Suma de unidades vendidas")
with r3c3:
    render_card("Prom ventas * día 30", fmt_number(prom_dia_30, 2), "und vendidas 30 días / 30")
with r3c4:
    render_status_card("Quiebre stock 30 días", quiebre_30_prom)

with st.container():
    st.markdown('<div class="filter-box">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Filtros</div>', unsafe_allow_html=True)

    f1, f2, f3, f4 = st.columns(4)
    with f1:
        cuentaes = ["Todos"]
        if col_cuenta:
            cuentaes += sorted(df_base[col_cuenta].dropna().astype(str).unique().tolist())
        filtro_cuenta = st.selectbox("cuenta", cuentaes)

    with f2:
        filtro_sku = st.text_input("SKU")

    with f3:
        filtro_titulo = st.text_input("Título")

    with f4:
        filtro_sku_variante = st.text_input("SKU Variante")

    csv_buffer = io.BytesIO()
    st.session_state.inv_filtrado.to_csv(csv_buffer, index=False, encoding="utf-8-sig")

    st.markdown('<div class="filter-actions">', unsafe_allow_html=True)
    b1, b2, b3 = st.columns(3)
    with b1:
        st.markdown('<div class="visual-btn">', unsafe_allow_html=True)
        aplicar = st.button("Aplicar filtros", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with b2:
        st.markdown('<div class="visual-btn secondary">', unsafe_allow_html=True)
        limpiar = st.button("Limpiar filtros", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with b3:
        st.markdown('<div class="visual-btn export">', unsafe_allow_html=True)
        st.download_button(
            "Exportar CSV",
            data=csv_buffer.getvalue(),
            file_name="informe_inventarios.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

if limpiar:
    st.session_state.inv_filtrado = st.session_state.inv_base.copy()
    st.rerun()

if aplicar:
    vista = df_base.copy()

    if col_cuenta and filtro_cuenta != "Todos":
        vista = vista[vista[col_cuenta].astype(str) == str(filtro_cuenta)]

    if col_sku and filtro_sku.strip():
        vista = vista[vista[col_sku].astype(str).str.contains(filtro_sku.strip(), case=False, na=False)]

    if col_titulo and filtro_titulo.strip():
        vista = vista[vista[col_titulo].astype(str).str.contains(filtro_titulo.strip(), case=False, na=False)]

    if col_sku_variante and filtro_sku_variante.strip():
        vista = vista[vista[col_sku_variante].astype(str).str.contains(filtro_sku_variante.strip(), case=False, na=False)]

    st.session_state.inv_filtrado = vista.copy()
    st.rerun()

df_vista = st.session_state.inv_filtrado.copy()

st.markdown("### Tabla")
st.caption("tabla resumen")

columnas_ocultar = [
    "dias_cobertura",
    "rotacion",
    "estado_stock",
]

df_tabla = df_vista.drop(
    columns=[c for c in columnas_ocultar if c in df_vista.columns],
    errors="ignore"
)

st.dataframe(df_tabla, use_container_width=True, height=700)
