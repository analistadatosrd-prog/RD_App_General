from io import BytesIO
from datetime import timedelta

import pandas as pd
import streamlit as st

from services.db import fetch_all, execute_query

st.set_page_config(
    page_title="Reporte de Cambios",
    page_icon="📝",
    layout="wide",
)

st.title("Reporte de Cambios")
st.caption("Seguimiento de cambios y comparación antes vs después por publicación.")
st.markdown("---")

RESPONSABLES_CAMBIO = [
    "andres",
    "coco",
    # agrega o quita opciones aquí
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
]


def init_state():
    defaults = {
        "rc_df_base": pd.DataFrame(),
        "rc_df_vista": pd.DataFrame(),
        "rc_f_id": "",
        "rc_f_cuenta": "Todas",
        "rc_f_titulo_meli": "",
        "rc_f_estado_publicacion": "Todas",
        "rc_f_logistica": "Todas",
        "rc_f_sku": "",
        "rc_f_titulo_ecom": "",
        "rc_f_campaign_ads": "Todas",
        "rc_f_estado_ads": "Todas",
        "rc_f_categoria": "Todas",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def cargar_datos():
    rows = fetch_all("SELECT * FROM rd_tabla_reporte_cambios")
    df = pd.DataFrame(rows) if rows else pd.DataFrame()

    if not df.empty:
        for col in [
            "fecha",
            "fecha_cambio",
            "fecha_resultados",
        ]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.date

    st.session_state.rc_df_base = df.copy()
    st.session_state.rc_df_vista = df.copy()


def options_from_column(df: pd.DataFrame, col: str):
    if df.empty or col not in df.columns:
        return ["Todas"]
    vals = sorted([str(x) for x in df[col].dropna().unique().tolist() if str(x).strip()])
    return ["Todas"] + vals


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


def aplicar_filtros():
    df = st.session_state.rc_df_base.copy()

    if df.empty:
        st.session_state.rc_df_vista = df
        return

    if st.session_state.rc_f_id.strip() and "id" in df.columns:
        df = df[df["id"].astype(str).str.contains(st.session_state.rc_f_id.strip(), case=False, na=False)]

    if st.session_state.rc_f_cuenta != "Todas" and "cuenta" in df.columns:
        df = df[df["cuenta"].astype(str) == st.session_state.rc_f_cuenta]

    if st.session_state.rc_f_titulo_meli.strip() and "titulo_meli" in df.columns:
        df = df[df["titulo_meli"].astype(str).str.contains(st.session_state.rc_f_titulo_meli.strip(), case=False, na=False)]

    if st.session_state.rc_f_estado_publicacion != "Todas" and "estado_publicacion" in df.columns:
        df = df[df["estado_publicacion"].astype(str) == st.session_state.rc_f_estado_publicacion]

    if st.session_state.rc_f_logistica != "Todas" and "logistica" in df.columns:
        df = df[df["logistica"].astype(str) == st.session_state.rc_f_logistica]

    if st.session_state.rc_f_sku.strip() and "sku" in df.columns:
        df = df[df["sku"].astype(str).str.contains(st.session_state.rc_f_sku.strip(), case=False, na=False)]

    if st.session_state.rc_f_titulo_ecom.strip() and "titulo_ecom" in df.columns:
        df = df[df["titulo_ecom"].astype(str).str.contains(st.session_state.rc_f_titulo_ecom.strip(), case=False, na=False)]

    if st.session_state.rc_f_campaign_ads != "Todas" and "campaign_ads" in df.columns:
        df = df[df["campaign_ads"].astype(str) == st.session_state.rc_f_campaign_ads]

    if st.session_state.rc_f_estado_ads != "Todas" and "estado_ads" in df.columns:
        df = df[df["estado_ads"].astype(str) == st.session_state.rc_f_estado_ads]

    if st.session_state.rc_f_categoria != "Todas" and "categoria" in df.columns:
        df = df[df["categoria"].astype(str) == st.session_state.rc_f_categoria]

    st.session_state.rc_df_vista = df.copy()


def limpiar_filtros():
    st.session_state.rc_f_id = ""
    st.session_state.rc_f_cuenta = "Todas"
    st.session_state.rc_f_titulo_meli = ""
    st.session_state.rc_f_estado_publicacion = "Todas"
    st.session_state.rc_f_logistica = "Todas"
    st.session_state.rc_f_sku = ""
    st.session_state.rc_f_titulo_ecom = ""
    st.session_state.rc_f_campaign_ads = "Todas"
    st.session_state.rc_f_estado_ads = "Todas"
    st.session_state.rc_f_categoria = "Todas"
    aplicar_filtros()


def agrupador_publicaciones(df: pd.DataFrame):
    if df.empty:
        return df

    df = df.copy()
    if "fecha" in df.columns:
        df["fecha_sort"] = pd.to_datetime(df["fecha"], errors="coerce")
    else:
        df["fecha_sort"] = pd.NaT

    base = (
        df.sort_values(["id", "fecha_sort"], ascending=[True, False])
        .groupby("id", as_index=False)
        .first()
    )

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

    eventos = eventos.sort_values(
        ["fecha_cambio_sort", "fecha_sort"],
        ascending=[False, False],
    )

    return eventos


def delta_text(actual, referencia, money=False, pct=False):
    a = safe_float(actual)
    b = safe_float(referencia)
    d = a - b

    if money:
        texto = fmt_money(d)
    elif pct:
        texto = fmt_pct(d)
    else:
        texto = fmt_num(d, 2)

    if d > 0:
        return f"↑ {texto}", "normal"
    if d < 0:
        return f"↓ {texto}", "inverse"
    return f"= {texto}", "off"


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

    execute_query(query, tuple(valores))


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


def mostrar_resumen_publicacion(row: pd.Series):
    ventas_ads = safe_float(row.get("ventas_publicidad"))
    ventas_org = safe_float(row.get("ventas_organicas"))
    total_ventas = ventas_ads + ventas_org

    cont = st.container(border=True)
    with cont:
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
            st.caption(f"Cuenta: {row.get('cuenta', '')} | Estado: {row.get('estado_publicacion', '')}")
            if row.get("enlace_meli"):
                st.link_button("Abrir publicación", row.get("enlace_meli"), use_container_width=False)

        with c4:
            a1, a2, a3 = st.columns(3)
            a1.metric("Ventas Ads", fmt_num(ventas_ads, 0))
            a2.metric("Ventas Orgánicas", fmt_num(ventas_org, 0))
            a3.metric("Total", fmt_num(total_ventas, 0))


def mostrar_vs_categoria(registro: pd.Series):
    st.markdown("#### Indicadores vs categoría")

    c1, c2, c3 = st.columns(3)
    c1.metric(
        "CTR publicación",
        fmt_pct(registro.get("ctr")),
        delta=delta_text(registro.get("ctr"), registro.get("ctr_categoria"), pct=True)[0],
    )
    c2.metric(
        "CVR publicación",
        fmt_pct(registro.get("cvr")),
        delta=delta_text(registro.get("cvr"), registro.get("cvr_categoria"), pct=True)[0],
    )
    c3.metric(
        "ACOS publicación",
        fmt_pct(registro.get("acos")),
        delta=delta_text(registro.get("acos"), registro.get("acos_categoria"), pct=True)[0],
    )

    d1, d2, d3 = st.columns(3)
    d1.metric("CTR categoría", fmt_pct(registro.get("ctr_categoria")))
    d2.metric("CVR categoría", fmt_pct(registro.get("cvr_categoria")))
    d3.metric("ACOS categoría", fmt_pct(registro.get("acos_categoria")))


def mostrar_kpis_base(registro: pd.Series):
    st.markdown("#### KPIs base")

    r1 = st.columns(5)
    r1[0].metric("Clicks", fmt_num(registro.get("clicks"), 0))
    r1[1].metric("Impresiones", fmt_num(registro.get("impresiones"), 0))
    r1[2].metric("Inversión", fmt_money(registro.get("inversion")))
    r1[3].metric("Ingresos Ads", fmt_money(registro.get("ingresos_ads")))
    r1[4].metric("Ingresos Totales", fmt_money(registro.get("ingresos_totales")))

    r2 = st.columns(4)
    r2[0].metric("Ventas Directas", fmt_num(registro.get("ventas_directas"), 0))
    r2[1].metric("Ventas Indirectas", fmt_num(registro.get("ventas_indirectas"), 0))
    r2[2].metric("Ventas Publicidad", fmt_num(registro.get("ventas_publicidad"), 0))
    r2[3].metric("Ventas Orgánicas", fmt_num(registro.get("ventas_organicas"), 0))


def mostrar_evento(evento: pd.Series, idx: int):
    etapa = str(evento.get("etapa_cambio") or "sin cambios").strip().lower()
    titulo = f"Evento {idx + 1} | {evento.get('etapa_cambio', 'sin cambios')} | {evento.get('fecha_cambio', '-')}"
    with st.expander(titulo, expanded=False):
        st.markdown(f"**Responsable:** {evento.get('responsable', '-')}")
        st.markdown(f"**Cambio realizado:** {evento.get('cambio_realizado', '-')}")
        st.markdown(f"**Fecha resultados:** {evento.get('fecha_resultados', '-')}")

        if etapa == "con resultados":
            st.markdown("##### Comparativa antes vs después")

            a1, a2, a3, a4 = st.columns(4)
            a1.metric(
                "Clicks",
                fmt_num(evento.get("clicks_resultado"), 0),
                delta=fmt_num(safe_float(evento.get("clicks_resultado")) - safe_float(evento.get("clicks")), 0),
            )
            a2.metric(
                "Impresiones",
                fmt_num(evento.get("impresiones_resultado"), 0),
                delta=fmt_num(safe_float(evento.get("impresiones_resultado")) - safe_float(evento.get("impresiones")), 0),
            )
            a3.metric(
                "Inversión",
                fmt_money(evento.get("inversion_resultado")),
                delta=fmt_money(safe_float(evento.get("inversion_resultado")) - safe_float(evento.get("inversion"))),
            )
            a4.metric(
                "Ingresos Ads",
                fmt_money(evento.get("ingresos_ads_resultado")),
                delta=fmt_money(safe_float(evento.get("ingresos_ads_resultado")) - safe_float(evento.get("ingresos_ads"))),
            )

            b1, b2, b3, b4 = st.columns(4)
            b1.metric(
                "Ingresos Totales",
                fmt_money(evento.get("ingresos_totales_resultado")),
                delta=fmt_money(safe_float(evento.get("ingresos_totales_resultado")) - safe_float(evento.get("ingresos_totales"))),
            )
            b2.metric(
                "Ventas Directas",
                fmt_num(evento.get("ventas_directas_resultado"), 0),
                delta=fmt_num(safe_float(evento.get("ventas_directas_resultado")) - safe_float(evento.get("ventas_directas")), 0),
            )
            b3.metric(
                "Ventas Indirectas",
                fmt_num(evento.get("ventas_indirectas_resultado"), 0),
                delta=fmt_num(safe_float(evento.get("ventas_indirectas_resultado")) - safe_float(evento.get("ventas_indirectas")), 0),
            )
            b4.metric(
                "Ventas Publicidad",
                fmt_num(evento.get("ventas_publicidad_resultado"), 0),
                delta=fmt_num(safe_float(evento.get("ventas_publicidad_resultado")) - safe_float(evento.get("ventas_publicidad")), 0),
            )

            c1, _ = st.columns(2)
            c1.metric(
                "Ventas Orgánicas",
                fmt_num(evento.get("ventas_organicas_resultado"), 0),
                delta=fmt_num(safe_float(evento.get("ventas_organicas_resultado")) - safe_float(evento.get("ventas_organicas")), 0),
            )
        else:
            st.info("Este cambio aún está en medición. Solo se muestra el cambio reportado.")


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

with st.container(border=True):
    st.markdown("### Filtros")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.text_input("ID", key="rc_f_id", placeholder="Buscar ID...", on_change=aplicar_filtros)
    with c2:
        st.selectbox("Cuenta", cuenta_opts, key="rc_f_cuenta", on_change=aplicar_filtros)
    with c3:
        st.text_input("Título Meli", key="rc_f_titulo_meli", placeholder="Buscar título...", on_change=aplicar_filtros)
    with c4:
        st.selectbox("Estado publicación", estado_pub_opts, key="rc_f_estado_publicacion", on_change=aplicar_filtros)

    d1, d2, d3, d4 = st.columns(4)
    with d1:
        st.selectbox("Logística", logistica_opts, key="rc_f_logistica", on_change=aplicar_filtros)
    with d2:
        st.text_input("SKU", key="rc_f_sku", placeholder="Buscar SKU...", on_change=aplicar_filtros)
    with d3:
        st.text_input("Título Ecom", key="rc_f_titulo_ecom", placeholder="Buscar título Ecom...", on_change=aplicar_filtros)
    with d4:
        st.selectbox("Campaign Ads", campaign_opts, key="rc_f_campaign_ads", on_change=aplicar_filtros)

    e1, e2, e3 = st.columns([1, 1, 2])
    with e1:
        st.selectbox("Estado Ads", estado_ads_opts, key="rc_f_estado_ads", on_change=aplicar_filtros)
    with e2:
        st.selectbox("Categoría", categoria_opts, key="rc_f_categoria", on_change=aplicar_filtros)
    with e3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Limpiar filtros", use_container_width=True):
            limpiar_filtros()
            st.rerun()

aplicar_filtros()
df_vista = st.session_state.rc_df_vista

publicaciones = agrupador_publicaciones(df_vista)

m1, m2, m3 = st.columns(3)
m1.metric("Publicaciones visibles", len(publicaciones))
m2.metric("Registros filtrados", len(df_vista))
m3.metric("Eventos medibles", len(df_base[df_base["etapa_cambio"].astype(str).str.lower().isin(["en medicion", "con resultados"])]))

st.markdown("### Descargas")
descargable = df_base[
    df_base["etapa_cambio"].astype(str).str.lower().isin(["en medicion", "con resultados"])
].copy()

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
        st.button(
            "Descargar Excel",
            disabled=True,
            use_container_width=True,
            help="No fue posible generar el archivo Excel.",
        )

st.markdown("---")
st.markdown("### Publicaciones")

if publicaciones.empty:
    st.info("No hay publicaciones para mostrar con los filtros actuales.")
    st.stop()

for idx, row in publicaciones.iterrows():
    mostrar_resumen_publicacion(row)

    label = f"{row.get('titulo_meli', '')} | {row.get('id', '')}"
    with st.expander(f"Ver detalle | {label}", expanded=False):
        k1, k2 = st.columns([2.3, 1.2])

        with k1:
            mostrar_kpis_base(row)
            mostrar_vs_categoria(row)

        with k2:
            st.markdown("#### Datos generales")
            st.markdown(f"**Cuenta:** {row.get('cuenta', '-')}")
            st.markdown(f"**Estado publicación:** {row.get('estado_publicacion', '-')}")
            st.markdown(f"**Logística:** {row.get('logistica', '-')}")
            st.markdown(f"**Campaign Ads:** {row.get('campaign_ads', '-')}")
            st.markdown(f"**Estado Ads:** {row.get('estado_ads', '-')}")
            st.markdown(f"**Categoría:** {row.get('categoria', '-')}")
            st.markdown(f"**Fecha base:** {row.get('fecha', '-')}")

        st.markdown("---")
        st.markdown("#### Reportar cambio")

        with st.form(key=f"form_cambio_{idx}"):
            f1, f2 = st.columns(2)
            with f1:
                fecha_cambio = st.date_input(
                    "Fecha cambio",
                    value=pd.Timestamp.today().date(),
                    format="YYYY-MM-DD",
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
        st.markdown("#### Eventos de cambios y resultados")

        eventos = obtener_eventos_por_id(df_base, row.get("id"))
        eventos = eventos[
            eventos["etapa_cambio"].astype(str).str.lower().isin(["en medicion", "con resultados"])
        ].copy()

        if eventos.empty:
            st.caption("Esta publicación aún no tiene eventos registrados.")
        else:
            for ev_idx, (_, evento) in enumerate(eventos.iterrows()):
                mostrar_evento(evento, ev_idx)
