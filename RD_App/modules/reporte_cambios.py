from io import BytesIO
from datetime import timedelta

import pandas as pd
import streamlit as st

from services.db import fetch_all, execute

st.set_page_config(
    page_title="Reporte de Cambios",
    page_icon="📝",
    layout="wide",
)

st.markdown("""
<style>
.vs-card{
    border:1px solid rgba(49,51,63,0.18);
    border-radius:12px;
    padding:12px 14px;
    margin-bottom:10px;
    background:#ffffff;
}
.vs-label{
    font-size:0.85rem;
    color:#6b7280;
    margin-bottom:6px;
    font-weight:600;
}
.vs-row{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:14px;
}
.vs-value{
    font-size:1.35rem;
    font-weight:700;
    color:#111827;
    line-height:1.1;
    white-space:nowrap;
}
.vs-delta{
    font-size:0.95rem;
    font-weight:700;
    white-space:nowrap;
}
.vs-up{ color:#16a34a; }
.vs-down{ color:#dc2626; }
.vs-flat{ color:#6b7280; }
</style>
""", unsafe_allow_html=True)

st.title("Reporte de Cambios")
st.caption("Seguimiento de cambios y comparación antes vs después por publicación.")
st.markdown("---")

RESPONSABLES_CAMBIO = [
    "andres",
    "coco",
    "valeria",
    "ezeqiel",
    "monica",
]

COLUMNAS_TABLA = [
    "id",
    "cuenta",
    "titulo_meli",
    "enlace_meli",
    "imagen_portada",
    "estado_publicacion",
    "logistica",
    "sku",
    "titulo_ecom",
    "campaign_ads",
    "estado_ads",
    "categoria",
    "fecha",
    "clicks",
    "impresiones",
    "inversion",
    "ingresos_directos",
    "ingresos_indirectos",
    "ingresos_ads",
    "ingresos_totales",
    "ventas_directas",
    "ventas_indirectas",
    "ventas_publicidad",
    "ventas_organicas",
    "ctr",
    "cvr",
    "acos",
    "ctr_categoria",
    "cvr_categoria",
    "acos_categoria",
    "ratio_venta_organica",
    "ratio_venta_ads",
    "ratio_venta_organica_categoria",
    "ratio_venta_ads_categoria",
    "fecha_cambio",
    "responsable",
    "cambio_realizado",
    "fecha_resultados",
    "imagen_logistica",
    "etapa_cambio",
    "clicks_resultado",
    "impresiones_resultado",
    "inversion_resultado",
    "ingresos_directos_resultado",
    "ingresos_indirectos_resultado",
    "ingresos_ads_resultado",
    "ingresos_totales_resultado",
    "ventas_directas_resultado",
    "ventas_indirectas_resultado",
    "ventas_publicidad_resultado",
    "ventas_organicas_resultado",
    "ratio_venta_organica_resultado",
    "ratio_venta_ads_resultado",
]

KPI_COMPARACION = [
    ("ctr", "CTR", "pct"),
    ("cvr", "CVR", "pct"),
    ("acos", "ACOS", "pct"),
    ("ratio_venta_organica", "Ratio Venta Orgánica", "plain"),
    ("ratio_venta_ads", "Ratio Venta Ads", "plain"),
]


def init_state():
    defaults = {
        "rc_df_base": pd.DataFrame(),
        "rc_df_vista": pd.DataFrame(),
        "rc_limite_vista": 5,
        "rc_filters_nonce": 0,
        "rc_filter_values": {
            "id": "",
            "cuenta": "Todas",
            "titulo_meli": "",
            "estado_publicacion": "Todas",
            "logistica": "Todas",
            "sku": "",
            "titulo_ecom": "",
            "campaign_ads": "Todas",
            "estado_ads": "Todas",
            "categoria": "Todas",
            "etapa_cambio": "Todas",
            "responsable": "Todos",
        },
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def cargar_datos():
    rows = fetch_all("SELECT * FROM rd_tabla_reporte_cambios")
    df = pd.DataFrame(rows) if rows else pd.DataFrame()

    if not df.empty:
        for col in ["fecha", "fecha_cambio", "fecha_resultados"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.date

    st.session_state.rc_df_base = df.copy()
    st.session_state.rc_df_vista = df.copy()


def options_from_column(df: pd.DataFrame, col: str, all_label="Todas"):
    if df.empty or col not in df.columns:
        return [all_label]
    vals = sorted([str(x) for x in df[col].dropna().unique().tolist() if str(x).strip()])
    return [all_label] + vals


def safe_float(value):
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def fmt_num(value, decimals=0):
    try:
        if pd.isna(value):
            return "-"
        return f"{float(value):,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "-"


def fmt_money(value):
    try:
        if pd.isna(value):
            return "-"
        return f"$ {float(value):,.0f}".replace(",", ".")
    except Exception:
        return "-"


def fmt_pct(value):
    try:
        if pd.isna(value):
            return "-"
        return f"{float(value):,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "-"


def fmt_plain(value, decimals=2):
    try:
        if pd.isna(value):
            return "-"
        return f"{float(value):,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "-"


def fmt_by_type(value, value_type):
    if value_type == "money":
        return fmt_money(value)
    if value_type == "pct":
        return fmt_pct(value)
    if value_type == "plain":
        return fmt_plain(value, 2)
    return fmt_num(value, 0)


def pct_change(base, comp):
    b = safe_float(base)
    c = safe_float(comp)
    if b == 0:
        return None
    return ((c - b) / b) * 100


def leer_filtros_desde_widgets():
    nonce = st.session_state.rc_filters_nonce
    st.session_state.rc_filter_values = {
        "id": st.session_state.get(f"rc_f_id_{nonce}", ""),
        "cuenta": st.session_state.get(f"rc_f_cuenta_{nonce}", "Todas"),
        "titulo_meli": st.session_state.get(f"rc_f_titulo_meli_{nonce}", ""),
        "estado_publicacion": st.session_state.get(f"rc_f_estado_publicacion_{nonce}", "Todas"),
        "logistica": st.session_state.get(f"rc_f_logistica_{nonce}", "Todas"),
        "sku": st.session_state.get(f"rc_f_sku_{nonce}", ""),
        "titulo_ecom": st.session_state.get(f"rc_f_titulo_ecom_{nonce}", ""),
        "campaign_ads": st.session_state.get(f"rc_f_campaign_ads_{nonce}", "Todas"),
        "estado_ads": st.session_state.get(f"rc_f_estado_ads_{nonce}", "Todas"),
        "categoria": st.session_state.get(f"rc_f_categoria_{nonce}", "Todas"),
        "etapa_cambio": st.session_state.get(f"rc_f_etapa_cambio_{nonce}", "Todas"),
        "responsable": st.session_state.get(f"rc_f_responsable_{nonce}", "Todos"),
    }


def aplicar_filtros():
    leer_filtros_desde_widgets()
    filtros = st.session_state.rc_filter_values
    df = st.session_state.rc_df_base.copy()

    if df.empty:
        st.session_state.rc_df_vista = df
        return

    if filtros["id"].strip() and "id" in df.columns:
        df = df[df["id"].astype(str).str.contains(filtros["id"].strip(), case=False, na=False)]

    if filtros["cuenta"] != "Todas" and "cuenta" in df.columns:
        df = df[df["cuenta"].astype(str) == filtros["cuenta"]]

    if filtros["titulo_meli"].strip() and "titulo_meli" in df.columns:
        df = df[df["titulo_meli"].astype(str).str.contains(filtros["titulo_meli"].strip(), case=False, na=False)]

    if filtros["estado_publicacion"] != "Todas" and "estado_publicacion" in df.columns:
        df = df[df["estado_publicacion"].astype(str) == filtros["estado_publicacion"]]

    if filtros["logistica"] != "Todas" and "logistica" in df.columns:
        df = df[df["logistica"].astype(str) == filtros["logistica"]]

    if filtros["sku"].strip() and "sku" in df.columns:
        df = df[df["sku"].astype(str).str.contains(filtros["sku"].strip(), case=False, na=False)]

    if filtros["titulo_ecom"].strip() and "titulo_ecom" in df.columns:
        df = df[df["titulo_ecom"].astype(str).str.contains(filtros["titulo_ecom"].strip(), case=False, na=False)]

    if filtros["campaign_ads"] != "Todas" and "campaign_ads" in df.columns:
        df = df[df["campaign_ads"].astype(str) == filtros["campaign_ads"]]

    if filtros["estado_ads"] != "Todas" and "estado_ads" in df.columns:
        df = df[df["estado_ads"].astype(str) == filtros["estado_ads"]]

    if filtros["categoria"] != "Todas" and "categoria" in df.columns:
        df = df[df["categoria"].astype(str) == filtros["categoria"]]

    if filtros["etapa_cambio"] != "Todas" and "etapa_cambio" in df.columns:
        df = df[df["etapa_cambio"].astype(str) == filtros["etapa_cambio"]]

    if filtros["responsable"] != "Todos" and "responsable" in df.columns:
        df = df[df["responsable"].astype(str) == filtros["responsable"]]

    st.session_state.rc_df_vista = df.copy()


def limpiar_filtros():
    st.session_state.rc_filter_values = {
        "id": "",
        "cuenta": "Todas",
        "titulo_meli": "",
        "estado_publicacion": "Todas",
        "logistica": "Todas",
        "sku": "",
        "titulo_ecom": "",
        "campaign_ads": "Todas",
        "estado_ads": "Todas",
        "categoria": "Todas",
        "etapa_cambio": "Todas",
        "responsable": "Todos",
    }
    st.session_state.rc_filters_nonce += 1


def calcular_ventas_totales(df: pd.DataFrame):
    df = df.copy()
    if "ventas_publicidad" not in df.columns:
        df["ventas_publicidad"] = 0
    if "ventas_organicas" not in df.columns:
        df["ventas_organicas"] = 0
    df["ventas_totales_calc"] = (
        pd.to_numeric(df["ventas_publicidad"], errors="coerce").fillna(0)
        + pd.to_numeric(df["ventas_organicas"], errors="coerce").fillna(0)
    )
    return df


def agrupador_publicaciones(df: pd.DataFrame):
    if df.empty:
        return df

    df = df.copy()
    df = calcular_ventas_totales(df)

    if "fecha" in df.columns:
        df["fecha_sort"] = pd.to_datetime(df["fecha"], errors="coerce")
    else:
        df["fecha_sort"] = pd.NaT

    base = (
        df.sort_values(["id", "fecha_sort"], ascending=[True, False])
        .groupby("id", as_index=False)
        .first()
    )

    base["logistica_sort"] = (
        base.get("logistica", pd.Series([""] * len(base)))
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("fulfillment")
        .astype(int)
    )

    base = base.sort_values(
        by=["logistica_sort", "ventas_totales_calc", "fecha_sort"],
        ascending=[False, False, False]
    ).reset_index(drop=True)

    return base


def obtener_eventos_por_id(df: pd.DataFrame, pub_id: str):
    if df.empty or "id" not in df.columns:
        return pd.DataFrame()

    eventos = df[df["id"].astype(str) == str(pub_id)].copy()

    if "fecha_cambio" in eventos.columns:
        eventos["fecha_cambio_sort"] = pd.to_datetime(eventos["fecha_cambio"], errors="coerce")
    else:
        eventos["fecha_cambio_sort"] = pd.NaT

    if "fecha" in eventos.columns:
        eventos["fecha_sort"] = pd.to_datetime(eventos["fecha"], errors="coerce")
    else:
        eventos["fecha_sort"] = pd.NaT

    return eventos.sort_values(["fecha_cambio_sort", "fecha_sort"], ascending=[False, False])


def preparar_insert_desde_registro(registro: dict, fecha_cambio, responsable, cambio_realizado):
    nuevo = {}
    for col in COLUMNAS_TABLA:
        nuevo[col] = registro.get(col, None)

    nuevo["fecha_cambio"] = fecha_cambio
    nuevo["responsable"] = responsable
    nuevo["cambio_realizado"] = cambio_realizado
    nuevo["fecha_resultados"] = fecha_cambio + timedelta(days=7)
    nuevo["etapa_cambio"] = "en medicion"

    return nuevo


def insertar_copia_con_cambio(registro: dict, fecha_cambio, responsable, cambio_realizado):
    data = preparar_insert_desde_registro(registro, fecha_cambio, responsable, cambio_realizado)

    columnas = list(data.keys())
    placeholders = ", ".join(["%s"] * len(columnas))
    columnas_sql = ", ".join(columnas)
    valores = [data[c] for c in columnas]

    query = f"""
        INSERT INTO rd_tabla_reporte_cambios ({columnas_sql})
        VALUES ({placeholders})
    """
    execute(query, tuple(valores))


@st.cache_data
def convert_df_to_csv(df: pd.DataFrame):
    return df.to_csv(index=False).encode("utf-8-sig")


def convert_df_to_excel(df: pd.DataFrame):
    buffer = BytesIO()
    try:
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="reporte_cambios")
    except Exception:
        try:
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="reporte_cambios")
        except Exception:
            return None
    return buffer.getvalue()


def render_vs_item(label, value, delta, inverse=False):
    if delta is None:
        delta_txt = "→ 0,00%"
        delta_class = "vs-flat"
    else:
        if inverse:
            if delta < 0:
                delta_txt = f"↓ {abs(delta):.2f}%".replace(".", ",")
                delta_class = "vs-up"
            elif delta > 0:
                delta_txt = f"↑ {delta:.2f}%".replace(".", ",")
                delta_class = "vs-down"
            else:
                delta_txt = "→ 0,00%"
                delta_class = "vs-flat"
        else:
            if delta > 0:
                delta_txt = f"↑ {delta:.2f}%".replace(".", ",")
                delta_class = "vs-up"
            elif delta < 0:
                delta_txt = f"↓ {abs(delta):.2f}%".replace(".", ",")
                delta_class = "vs-down"
            else:
                delta_txt = "→ 0,00%"
                delta_class = "vs-flat"

    html = f"""
    <div class="vs-card">
        <div class="vs-label">{label}</div>
        <div class="vs-row">
            <div class="vs-value">{value}</div>
            <div class="vs-delta {delta_class}">{delta_txt}</div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def mostrar_resumen_publicacion(row: pd.Series):
    total_ventas = safe_float(row.get("ventas_totales_calc"))

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([0.6, 1.1, 4.5, 2.2])

        with c1:
            img_log = row.get("imagen_logistica")
            if img_log:
                st.image(img_log, width=36)

        with c2:
            img_prod = row.get("imagen_portada")
            if img_prod:
                st.image(img_prod, width=90)

        with c3:
            st.markdown(f"**{row.get('titulo_meli', '')}**")
            st.caption(f"ID: {row.get('id', '')} | SKU: {row.get('sku', '')}")
            st.caption(
                f"Cuenta: {row.get('cuenta', '')} | Estado: {row.get('estado_publicacion', '')} | "
                f"Logística: {row.get('logistica', '')} | Etapa: {row.get('etapa_cambio', '')}"
            )
            st.caption(f"Responsable: {row.get('responsable', '')}")
            if row.get("enlace_meli"):
                st.link_button("Abrir publicación", row.get("enlace_meli"), use_container_width=False)

        with c4:
            a1, a2, a3 = st.columns(3)
            a1.metric("Vtas Ads", fmt_num(row.get("ventas_publicidad"), 0))
            a2.metric("Vtas Org", fmt_num(row.get("ventas_organicas"), 0))
            a3.metric("Vtas Totales", fmt_num(total_ventas, 0))


def render_datos_generales(registro: pd.Series):
    with st.container(border=True):
        st.markdown("#### Datos generales")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.write(f"**Cuenta:** {registro.get('cuenta', '-')}")
            st.write(f"**ID:** {registro.get('id', '-')}")
            st.write(f"**Responsable:** {registro.get('responsable', '-')}")
        with c2:
            st.write(f"**SKU:** {registro.get('sku', '-')}")
            st.write(f"**Categoría:** {registro.get('categoria', '-')}")
            st.write(f"**Etapa cambio:** {registro.get('etapa_cambio', '-')}")
        with c3:
            st.write(f"**Estado publicación:** {registro.get('estado_publicacion', '-')}")
            st.write(f"**Logística:** {registro.get('logistica', '-')}")
            st.write(f"**Fecha cambio:** {registro.get('fecha_cambio', '-')}")
        with c4:
            st.write(f"**Campaign Ads:** {registro.get('campaign_ads', '-')}")
            st.write(f"**Estado Ads:** {registro.get('estado_ads', '-')}")
            st.write(f"**Fecha resultados:** {registro.get('fecha_resultados', '-')}")


def render_metricas_generales(registro: pd.Series, suffix=""):
    with st.container(border=True):
        st.markdown("#### Métricas generales")

        fila_1 = [
            ("clicks", "Clicks", "num"),
            ("impresiones", "Impresiones", "num"),
            ("inversion", "Inversión", "money"),
        ]
        fila_2 = [
            ("ingresos_directos", "Ingresos Directos", "money"),
            ("ingresos_indirectos", "Ingresos Indirectos", "money"),
            ("ingresos_ads", "Ingresos Ads", "money"),
            ("ingresos_totales", "Ingresos Totales", "money"),
        ]
        fila_3 = [
            ("ventas_directas", "Ventas Directas", "num"),
            ("ventas_indirectas", "Ventas Indirectas", "num"),
            ("ventas_publicidad", "Ventas Publicidad", "num"),
            ("ventas_totales_calc", "Ventas Totales", "num"),
        ]

        cols1 = st.columns(3)
        for i, (key, label, vtype) in enumerate(fila_1):
            col_name = f"{key}{suffix}"
            cols1[i].metric(label, fmt_by_type(registro.get(col_name), vtype))

        cols2 = st.columns(4)
        for i, (key, label, vtype) in enumerate(fila_2):
            col_name = f"{key}{suffix}"
            cols2[i].metric(label, fmt_by_type(registro.get(col_name), vtype))

        cols3 = st.columns(4)
        for i, (key, label, vtype) in enumerate(fila_3):
            if suffix == "_resultado" and key == "ventas_totales_calc":
                total_resultado = safe_float(registro.get("ventas_organicas_resultado")) + safe_float(registro.get("ventas_publicidad_resultado"))
                cols3[i].metric(label, fmt_by_type(total_resultado, vtype))
            elif key == "ventas_totales_calc":
                total_base = safe_float(registro.get("ventas_organicas")) + safe_float(registro.get("ventas_publicidad"))
                cols3[i].metric(label, fmt_by_type(total_base, vtype))
            else:
                col_name = f"{key}{suffix}"
                cols3[i].metric(label, fmt_by_type(registro.get(col_name), vtype))


def render_kpis_base(registro: pd.Series):
    with st.container(border=True):
        st.markdown("#### KPIs base")
        for key, label, value_type in KPI_COMPARACION:
            st.metric(label, fmt_by_type(registro.get(key), value_type))


def render_kpis_categoria(registro: pd.Series):
    with st.container(border=True):
        st.markdown("#### KPIs categoría")
        mapeo = {
            "ctr": "ctr_categoria",
            "cvr": "cvr_categoria",
            "acos": "acos_categoria",
            "ratio_venta_organica": "ratio_venta_organica_categoria",
            "ratio_venta_ads": "ratio_venta_ads_categoria",
        }
        for key, label, value_type in KPI_COMPARACION:
            st.metric(label, fmt_by_type(registro.get(mapeo[key]), value_type))


def render_kpis_resultado(registro: pd.Series):
    with st.container(border=True):
        st.markdown("#### KPIs resultado")
        mapeo = {
            "ctr": "ctr_resultado",
            "cvr": "cvr_resultado",
            "acos": "acos_resultado",
            "ratio_venta_organica": "ratio_venta_organica_resultado",
            "ratio_venta_ads": "ratio_venta_ads_resultado",
        }
        for key, label, value_type in KPI_COMPARACION:
            st.metric(label, fmt_by_type(registro.get(mapeo[key]), value_type))


def render_vs_categoria(registro: pd.Series):
    with st.container(border=True):
        st.markdown("#### VS")
        pares = [
            ("CTR", registro.get("ctr_categoria"), registro.get("ctr"), "pct", False),
            ("CVR", registro.get("cvr_categoria"), registro.get("cvr"), "pct", False),
            ("ACOS", registro.get("acos_categoria"), registro.get("acos"), "pct", True),
            ("Ratio Venta Orgánica", registro.get("ratio_venta_organica_categoria"), registro.get("ratio_venta_organica"), "plain", False),
            ("Ratio Venta Ads", registro.get("ratio_venta_ads_categoria"), registro.get("ratio_venta_ads"), "plain", False),
        ]
        for label, base_val, comp_val, value_type, inverse in pares:
            render_vs_item(label, fmt_by_type(comp_val, value_type), pct_change(base_val, comp_val), inverse=inverse)


def render_vs_resultado(registro: pd.Series):
    with st.container(border=True):
        st.markdown("#### VS")
        pares = [
            ("CTR", registro.get("ctr"), registro.get("ctr_resultado"), "pct", False),
            ("CVR", registro.get("cvr"), registro.get("cvr_resultado"), "pct", False),
            ("ACOS", registro.get("acos"), registro.get("acos_resultado"), "pct", True),
            ("Ratio Venta Orgánica", registro.get("ratio_venta_organica"), registro.get("ratio_venta_organica_resultado"), "plain", False),
            ("Ratio Venta Ads", registro.get("ratio_venta_ads"), registro.get("ratio_venta_ads_resultado"), "plain", False),
        ]
        for label, base_val, comp_val, value_type, inverse in pares:
            render_vs_item(label, fmt_by_type(comp_val, value_type), pct_change(base_val, comp_val), inverse=inverse)


def render_detalle_publicacion(registro: pd.Series):
    render_datos_generales(registro)
    render_metricas_generales(registro)

    c1, c2, c3 = st.columns(3)
    with c1:
        render_kpis_base(registro)
    with c2:
        render_kpis_categoria(registro)
    with c3:
        render_vs_categoria(registro)


def render_resumen_medicion(evento: pd.Series):
    with st.container(border=True):
        st.markdown("#### Resumen KPI actual")
        cols = st.columns(4)
        resumen = [
            ("Clicks", fmt_num(evento.get("clicks"), 0)),
            ("Impresiones", fmt_num(evento.get("impresiones"), 0)),
            ("Ingresos Ads", fmt_money(evento.get("ingresos_ads"))),
            ("Ingresos Totales", fmt_money(evento.get("ingresos_totales"))),
        ]
        for i, (label, value) in enumerate(resumen):
            cols[i].metric(label, value)


def render_evento_en_medicion(evento: pd.Series):
    with st.container(border=True):
        st.markdown("#### Datos del evento")
        st.write(f"**Responsable:** {evento.get('responsable', '-')}")
        st.write(f"**Cambio realizado:** {evento.get('cambio_realizado', '-')}")
        st.write(f"**Etapa cambio:** {evento.get('etapa_cambio', '-')}")
        st.write(f"**Fecha cambio:** {evento.get('fecha_cambio', '-')}")
        st.write(f"**Fecha resultados:** {evento.get('fecha_resultados', '-')}")
    render_resumen_medicion(evento)


def asegurar_kpis_resultado(evento: pd.Series):
    evento = evento.copy()

    if "ctr_resultado" not in evento.index or pd.isna(evento.get("ctr_resultado")):
        clicks_r = safe_float(evento.get("clicks_resultado"))
        impresiones_r = safe_float(evento.get("impresiones_resultado"))
        evento["ctr_resultado"] = (clicks_r / impresiones_r * 100) if impresiones_r > 0 else None

    if "cvr_resultado" not in evento.index or pd.isna(evento.get("cvr_resultado")):
        ventas_pub_r = safe_float(evento.get("ventas_publicidad_resultado"))
        clicks_r = safe_float(evento.get("clicks_resultado"))
        evento["cvr_resultado"] = (ventas_pub_r / clicks_r * 100) if clicks_r > 0 else None

    if "acos_resultado" not in evento.index or pd.isna(evento.get("acos_resultado")):
        inv_r = safe_float(evento.get("inversion_resultado"))
        ing_ads_r = safe_float(evento.get("ingresos_ads_resultado"))
        evento["acos_resultado"] = (inv_r / ing_ads_r * 100) if ing_ads_r > 0 else None

    if "ratio_venta_organica_resultado" not in evento.index or pd.isna(evento.get("ratio_venta_organica_resultado")):
        vtas_org_r = safe_float(evento.get("ventas_organicas_resultado"))
        vtas_ads_r = safe_float(evento.get("ventas_publicidad_resultado"))
        total_r = vtas_org_r + vtas_ads_r
        evento["ratio_venta_organica_resultado"] = (vtas_org_r / total_r * 100) if total_r > 0 else None

    if "ratio_venta_ads_resultado" not in evento.index or pd.isna(evento.get("ratio_venta_ads_resultado")):
        vtas_org_r = safe_float(evento.get("ventas_organicas_resultado"))
        vtas_ads_r = safe_float(evento.get("ventas_publicidad_resultado"))
        total_r = vtas_org_r + vtas_ads_r
        evento["ratio_venta_ads_resultado"] = (vtas_ads_r / total_r * 100) if total_r > 0 else None

    return evento


def render_evento_con_resultado(evento: pd.Series):
    evento = asegurar_kpis_resultado(evento)

    with st.container(border=True):
        st.markdown("#### Datos del evento")
        st.write(f"**Responsable:** {evento.get('responsable', '-')}")
        st.write(f"**Cambio realizado:** {evento.get('cambio_realizado', '-')}")
        st.write(f"**Etapa cambio:** {evento.get('etapa_cambio', '-')}")
        st.write(f"**Fecha cambio:** {evento.get('fecha_cambio', '-')}")
        st.write(f"**Fecha resultados:** {evento.get('fecha_resultados', '-')}")

    render_metricas_generales(evento)
    st.markdown("#### Bloque resultado")
    render_metricas_generales(evento, suffix="_resultado")

    c1, c2, c3 = st.columns(3)
    with c1:
        render_kpis_base(evento)
    with c2:
        render_kpis_resultado(evento)
    with c3:
        render_vs_resultado(evento)


def mostrar_evento(evento: pd.Series, idx: int):
    etapa = str(evento.get("etapa_cambio") or "sin cambios").strip().lower()
    titulo = f"Evento {idx + 1} | {evento.get('etapa_cambio', 'sin cambios')} | {evento.get('fecha_cambio', '-')}"

    with st.expander(titulo, expanded=False):
        if etapa == "con resultados":
            render_evento_con_resultado(evento)
        else:
            render_evento_en_medicion(evento)


init_state()

if st.session_state.rc_df_base.empty:
    with st.spinner("Cargando tabla rd_tabla_reporte_cambios..."):
        cargar_datos()

df_base = st.session_state.rc_df_base

if df_base.empty:
    st.warning("La tabla rd_tabla_reporte_cambios no tiene datos disponibles.")
    st.stop()

cuenta_opts = options_from_column(df_base, "cuenta")
estado_pub_opts = options_from_column(df_base, "estado_publicacion")
logistica_opts = options_from_column(df_base, "logistica")
campaign_opts = options_from_column(df_base, "campaign_ads")
estado_ads_opts = options_from_column(df_base, "estado_ads")
categoria_opts = options_from_column(df_base, "categoria")
etapa_cambio_opts = options_from_column(df_base, "etapa_cambio")
responsable_opts = options_from_column(df_base, "responsable", all_label="Todos")

filtros = st.session_state.rc_filter_values
nonce = st.session_state.rc_filters_nonce

with st.container(border=True):
    st.markdown("### Filtros")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.text_input(
            "ID",
            key=f"rc_f_id_{nonce}",
            value=filtros["id"],
            placeholder="Buscar ID...",
            on_change=aplicar_filtros,
        )
    with c2:
        st.selectbox(
            "Cuenta",
            cuenta_opts,
            key=f"rc_f_cuenta_{nonce}",
            index=cuenta_opts.index(filtros["cuenta"]) if filtros["cuenta"] in cuenta_opts else 0,
            on_change=aplicar_filtros,
        )
    with c3:
        st.text_input(
            "Título Meli",
            key=f"rc_f_titulo_meli_{nonce}",
            value=filtros["titulo_meli"],
            placeholder="Buscar título...",
            on_change=aplicar_filtros,
        )
    with c4:
        st.selectbox(
            "Estado publicación",
            estado_pub_opts,
            key=f"rc_f_estado_publicacion_{nonce}",
            index=estado_pub_opts.index(filtros["estado_publicacion"]) if filtros["estado_publicacion"] in estado_pub_opts else 0,
            on_change=aplicar_filtros,
        )

    d1, d2, d3, d4 = st.columns(4)
    with d1:
        st.selectbox(
            "Logística",
            logistica_opts,
            key=f"rc_f_logistica_{nonce}",
            index=logistica_opts.index(filtros["logistica"]) if filtros["logistica"] in logistica_opts else 0,
            on_change=aplicar_filtros,
        )
    with d2:
        st.text_input(
            "SKU",
            key=f"rc_f_sku_{nonce}",
            value=filtros["sku"],
            placeholder="Buscar SKU...",
            on_change=aplicar_filtros,
        )
    with d3:
        st.text_input(
            "Título Ecom",
            key=f"rc_f_titulo_ecom_{nonce}",
            value=filtros["titulo_ecom"],
            placeholder="Buscar título Ecom...",
            on_change=aplicar_filtros,
        )
    with d4:
        st.selectbox(
            "Campaign Ads",
            campaign_opts,
            key=f"rc_f_campaign_ads_{nonce}",
            index=campaign_opts.index(filtros["campaign_ads"]) if filtros["campaign_ads"] in campaign_opts else 0,
            on_change=aplicar_filtros,
        )

    e1, e2, e3, e4 = st.columns(4)
    with e1:
        st.selectbox(
            "Estado Ads",
            estado_ads_opts,
            key=f"rc_f_estado_ads_{nonce}",
            index=estado_ads_opts.index(filtros["estado_ads"]) if filtros["estado_ads"] in estado_ads_opts else 0,
            on_change=aplicar_filtros,
        )
    with e2:
        st.selectbox(
            "Categoría",
            categoria_opts,
            key=f"rc_f_categoria_{nonce}",
            index=categoria_opts.index(filtros["categoria"]) if filtros["categoria"] in categoria_opts else 0,
            on_change=aplicar_filtros,
        )
    with e3:
        st.selectbox(
            "Etapa cambio",
            etapa_cambio_opts,
            key=f"rc_f_etapa_cambio_{nonce}",
            index=etapa_cambio_opts.index(filtros["etapa_cambio"]) if filtros["etapa_cambio"] in etapa_cambio_opts else 0,
            on_change=aplicar_filtros,
        )
    with e4:
        st.selectbox(
            "Responsable",
            responsable_opts,
            key=f"rc_f_responsable_{nonce}",
            index=responsable_opts.index(filtros["responsable"]) if filtros["responsable"] in responsable_opts else 0,
            on_change=aplicar_filtros,
        )

    f1, f2 = st.columns([1, 2])
    with f1:
        st.selectbox("Ver", [5, 10, 50, 100], key="rc_limite_vista")
    with f2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Limpiar filtros", use_container_width=True):
            limpiar_filtros()
            st.rerun()

aplicar_filtros()
df_vista = st.session_state.rc_df_vista
publicaciones = agrupador_publicaciones(df_vista)
publicaciones_visibles = publicaciones.head(int(st.session_state.rc_limite_vista))

m1, m2, m3 = st.columns(3)
with m1:
    st.metric("Publicaciones visibles", len(publicaciones_visibles))
with m2:
    st.metric("Total filtradas", len(publicaciones))
with m3:
    eventos_medibles = 0
    if "etapa_cambio" in df_base.columns:
        eventos_medibles = len(
            df_base[df_base["etapa_cambio"].astype(str).str.lower().isin(["en medicion", "con resultados"])]
        )
    st.metric("Eventos medibles", eventos_medibles)

st.markdown("### Descargas")

if "etapa_cambio" in df_base.columns:
    descargable = df_base[
        df_base["etapa_cambio"].astype(str).str.lower().isin(["en medicion", "con resultados"])
    ].copy()
else:
    descargable = pd.DataFrame()

x1, x2, _ = st.columns([1, 1, 4])
with x1:
    st.download_button(
        "Descargar CSV",
        data=convert_df_to_csv(descargable),
        file_name="reporte_cambios_eventos.csv",
        mime="text/csv",
        use_container_width=True,
    )

with x2:
    excel_bytes = convert_df_to_excel(descargable)
    if excel_bytes is not None:
        st.download_button(
            "Descargar Excel",
            data=excel_bytes,
            file_name="reporte_cambios_eventos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    else:
        st.button("Descargar Excel", disabled=True, use_container_width=True)

st.markdown("---")
st.markdown("### Publicaciones")

if publicaciones_visibles.empty:
    st.info("No hay publicaciones para mostrar con los filtros actuales.")
    st.stop()

for idx, row in publicaciones_visibles.iterrows():
    mostrar_resumen_publicacion(row)

    label = f"{row.get('titulo_meli', '')} | {row.get('id', '')}"
    with st.expander(f"Ver detalle | {label}", expanded=False):
        tab1, tab2 = st.tabs(["Detalles", "Eventos y cambios"])

        with tab1:
            render_detalle_publicacion(row)

        with tab2:
            st.markdown("#### Reportar cambio")

            with st.form(key=f"form_cambio_{idx}"):
                f1, f2 = st.columns(2)
                with f1:
                    fecha_cambio = st.date_input(
                        "Fecha cambio",
                        value=pd.Timestamp.today().date(),
                    )
                with f2:
                    responsable = st.selectbox(
                        "Responsable",
                        options=RESPONSABLES_CAMBIO,
                        key=f"responsable_{idx}",
                    )

                cambio_realizado = st.text_area(
                    "Cambio realizado",
                    placeholder="Describe el cambio aplicado a la publicación...",
                    key=f"cambio_realizado_{idx}",
                )

                fecha_resultados = fecha_cambio + timedelta(days=7)
                st.info(f"Fecha resultados automática: {fecha_resultados}")

                grabar = st.form_submit_button("Grabar cambio", use_container_width=True)

                if grabar:
                    if not cambio_realizado.strip():
                        st.error("Debes escribir el cambio realizado.")
                    else:
                        try:
                            insertar_copia_con_cambio(
                                registro=row.to_dict(),
                                fecha_cambio=fecha_cambio,
                                responsable=responsable,
                                cambio_realizado=cambio_realizado.strip(),
                            )
                            st.success("Cambio registrado correctamente.")
                            cargar_datos()
                            aplicar_filtros()
                            st.rerun()
                        except Exception as e:
                            st.error(f"No fue posible registrar el cambio: {e}")

            st.markdown("---")
            st.markdown("#### Eventos registrados")

            eventos = obtener_eventos_por_id(df_base, row.get("id"))
            if not eventos.empty and "etapa_cambio" in eventos.columns:
                eventos = eventos[
                    eventos["etapa_cambio"].astype(str).str.lower().isin(["en medicion", "con resultados"])
                ].copy()

            if eventos.empty:
                st.caption("Esta publicación aún no tiene eventos registrados.")
            else:
                for ev_idx, (_, evento) in enumerate(eventos.iterrows()):
                    mostrar_evento(evento, ev_idx)
