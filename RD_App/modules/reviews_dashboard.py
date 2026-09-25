from __future__ import annotations

import html
import math
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from services.reviews_data import (
    ReviewFilters,
    get_alerts,
    get_dashboard_metrics,
    get_date_bounds,
    get_filter_options,
    get_monthly_trend,
    get_offer_type_metrics,
    get_rating_distribution,
    get_reviews_page,
    get_top_rated,
)

PAGE_SIZE_OPTIONS = [25, 50, 100]
MAX_ALERTS = 10
MIN_REVIEWS_FOR_RANKING = 5


def format_number(value) -> str:
    return f"{int(value or 0):,}".replace(",", ".")


def format_decimal(value, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "N/D"
    return f"{float(value):.{digits}f}".replace(".", ",")


def safe_text(value, fallback="N/D", max_length=100) -> str:
    if value is None or pd.isna(value):
        return fallback
    text_value = str(value).strip() or fallback
    return html.escape(text_value[:max_length])


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .reviews-hero {padding:1.4rem 1.6rem;border-radius:18px;margin:0 0 1rem;
            background:linear-gradient(135deg,#0f172a 0%,#172554 55%,#0f766e 120%);
            border:1px solid #334155;}
        .reviews-hero h1 {color:#f8fafc;font-size:1.7rem;margin:0;}
        .reviews-hero p {color:#cbd5e1;margin:.35rem 0 0;}
        .metric-card {border-radius:16px;padding:1.05rem 1.15rem;min-height:132px;
            border:1px solid #26354f;background:#101b31;margin-bottom:.5rem;}
        .metric-card .metric-label {color:#94a3b8;font-size:.76rem;text-transform:uppercase;
            letter-spacing:.04em;font-weight:700;}
        .metric-card .metric-value {color:#f8fafc;font-size:2rem;line-height:1.25;
            font-weight:800;margin:.35rem 0 .15rem;}
        .metric-card .metric-caption {color:#cbd5e1;font-size:.8rem;}
        .metric-card.green {border-left:5px solid #10b981;}
        .metric-card.blue {border-left:5px solid #38bdf8;}
        .metric-card.amber {border-left:5px solid #f59e0b;}
        .metric-card.red {border-left:5px solid #fb7185;}
        .alert-card,.top-card {padding:.85rem 1rem;border-radius:12px;margin:.5rem 0;}
        .alert-card {background:#21172a;border:1px solid #5a2845;}
        .alert-card strong {color:#fda4af;}
        .top-card {background:#0d2929;border:1px solid #145f5a;}
        .top-card strong {color:#5eead4;}
        .alert-card small,.top-card small {color:#cbd5e1;}
        .filter-summary {padding:.75rem 1rem;border-radius:10px;color:#dbeafe;
            background:#14213d;border:1px solid #254878;margin:.6rem 0 1rem;font-size:.9rem;}
        .section-title {margin-top:1.4rem;color:#f8fafc;font-weight:800;font-size:1.15rem;}
        [data-testid="stSidebar"] .reviews-filter-panel {padding:.9rem;border-radius:14px;
            background:linear-gradient(145deg,#0f2d52 0%,#123e72 100%);
            border:1px solid #2d6db1;margin:.65rem 0 1rem;}
        [data-testid="stSidebar"] .reviews-filter-panel h3 {margin:0;color:#f8fafc;font-size:1rem;}
        [data-testid="stSidebar"] .reviews-filter-panel p {color:#bfdbfe;font-size:.76rem;
            line-height:1.35;margin:.35rem 0 0;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(label: str, value: str, caption: str, color_class: str) -> None:
    st.markdown(
        f'<div class="metric-card {color_class}">'
        f'<div class="metric-label">{html.escape(label)}</div>'
        f'<div class="metric-value">{html.escape(value)}</div>'
        f'<div class="metric-caption">{html.escape(caption)}</div></div>',
        unsafe_allow_html=True,
    )


def render_filters() -> ReviewFilters:
    options = get_filter_options()
    date_min, date_max = get_date_bounds()
    if "reviews_filter_version" not in st.session_state:
        st.session_state.reviews_filter_version = 0
    version = st.session_state.reviews_filter_version

    def widget_key(name: str) -> str:
        return f"reviews_{name}_{version}"

    with st.sidebar:
        st.markdown(
            '<div class="reviews-filter-panel"><h3>🎛️ Filtros de Reviews</h3>'
            '<p>Se aplican al tablero, alertas y explorador.</p></div>',
            unsafe_allow_html=True,
        )
        quick_range = st.selectbox(
            "Período",
            ["Todo el historial", "Últimos 7 días", "Últimos 30 días",
             "Últimos 90 días", "Año actual", "Rango personalizado"],
            key=widget_key("quick_range"),
        )
        if quick_range == "Todo el historial":
            selected_range = (date_min, date_max)
        elif quick_range == "Últimos 7 días":
            selected_range = (max(date_min, date_max - timedelta(days=6)), date_max)
        elif quick_range == "Últimos 30 días":
            selected_range = (max(date_min, date_max - timedelta(days=29)), date_max)
        elif quick_range == "Últimos 90 días":
            selected_range = (max(date_min, date_max - timedelta(days=89)), date_max)
        elif quick_range == "Año actual":
            selected_range = (max(date_min, date(date_max.year, 1, 1)), date_max)
        else:
            custom_range = st.date_input(
                "Rango de fechas", value=(date_min, date_max),
                min_value=date_min, max_value=date_max,
                key=widget_key("custom_date_range"),
            )
            if isinstance(custom_range, (tuple, list)) and len(custom_range) == 2:
                selected_range = (custom_range[0], custom_range[1])
            else:
                st.info("Selecciona ambas fechas para aplicar el rango.")
                selected_range = (date_min, date_max)

        with st.expander("Identificación y producto", expanded=True):
            ml_id = st.text_input("ML_ID", placeholder="Ej. MLA123456789", key=widget_key("ml_id"))
            sku = st.text_input("SKU", placeholder="Buscar SKU", key=widget_key("sku"))
            titulo_ecom = st.text_input(
                "Título e-commerce", placeholder="Buscar producto asociado",
                key=widget_key("titulo_ecom"),
            )
            titulo_meli = st.text_input(
                "Título Mercado Libre", placeholder="Buscar publicación",
                key=widget_key("titulo_meli"),
            )
        with st.expander("Cuenta y publicación", expanded=False):
            cuenta = st.multiselect("Cuenta", options["cuentas"], key=widget_key("cuenta"))
            estado_meli = st.multiselect(
                "Estado Mercado Libre", options["estados_meli"],
                key=widget_key("estado_meli"),
            )
            tipo_publicacion = st.multiselect(
                "Tipo de publicación", options["tipos_publicacion"],
                key=widget_key("tipo_publicacion"),
            )
            tipo_oferta = st.multiselect(
                "Tipo de oferta", options["tipos_oferta"],
                key=widget_key("tipo_oferta"),
            )
        with st.expander("Calificación", expanded=False):
            estrellas = st.multiselect(
                "Estrellas", [1, 2, 3, 4, 5],
                format_func=lambda value: f"{value} estrella(s)",
                key=widget_key("estrellas"),
            )
        if st.button(
            "↻ Restablecer filtros", use_container_width=True,
            type="secondary", key=widget_key("reset_filters"),
        ):
            st.session_state.reviews_filter_version += 1
            st.session_state.reviews_current_page = 1
            st.session_state.pop("reviews_page_size", None)
            st.rerun()

    return ReviewFilters(
        ml_id=ml_id, cuenta=cuenta,
        fecha_desde=selected_range[0], fecha_hasta=selected_range[1],
        estrellas=estrellas, estado_meli=estado_meli,
        titulo_ecom=titulo_ecom, sku=sku,
        tipo_publicacion=tipo_publicacion, titulo_meli=titulo_meli,
        tipo_oferta=tipo_oferta,
    )


def build_filter_summary(filters: ReviewFilters) -> str:
    parts = [f"📅 {filters.fecha_desde:%d/%m/%Y}–{filters.fecha_hasta:%d/%m/%Y}"]
    for label, value in (
        ("ML_ID contiene", filters.ml_id), ("Cuenta", filters.cuenta),
        ("Estrellas", filters.estrellas), ("Estado", filters.estado_meli),
        ("Título e-commerce", filters.titulo_ecom), ("SKU contiene", filters.sku),
        ("Publicación", filters.tipo_publicacion),
        ("Título Mercado Libre", filters.titulo_meli), ("Oferta", filters.tipo_oferta),
    ):
        if value:
            formatted = ", ".join(map(str, value)) if isinstance(value, list) else str(value)
            parts.append(f"{label}: {formatted}")
    return " &nbsp; • &nbsp; ".join(html.escape(part) for part in parts)


def render_dashboard(filters: ReviewFilters) -> None:
    metrics = get_dashboard_metrics(filters)
    st.markdown(
        f'<div class="filter-summary"><strong>Universo activo:</strong> '
        f'{build_filter_summary(filters)}</div>', unsafe_allow_html=True,
    )
    st.markdown('<div class="section-title">📊 Resumen del universo filtrado</div>',
                unsafe_allow_html=True)
    col_1, col_2, col_3, col_4 = st.columns(4)
    with col_1:
        render_metric_card(
            "Reviews analizadas", format_number(metrics["total_reviews"]),
            f"{format_number(metrics['publicaciones_unicas'])} publicaciones únicas", "blue",
        )
    with col_2:
        render_metric_card(
            "Calificación promedio", f"{format_decimal(metrics['promedio_estrellas'])} / 5",
            f"{format_number(metrics['skus_unicos'])} SKU asociados", "amber",
        )
    with col_3:
        render_metric_card(
            "Satisfacción (4–5★)", f"{format_decimal(metrics['porcentaje_satisfaccion'])}%",
            f"{format_number(metrics['positivas'])} reviews positivas", "green",
        )
    with col_4:
        render_metric_card(
            "Quejas críticas (1–2★)",
            f"{format_decimal(metrics['porcentaje_quejas_criticas'])}%",
            f"{format_number(metrics['quejas_criticas'])} reviews críticas", "red",
        )
    if not metrics["total_reviews"]:
        st.warning("No se encontraron reviews con los filtros seleccionados.")
        return

    st.markdown('<div class="section-title">📈 Comportamiento de calificaciones</div>',
                unsafe_allow_html=True)
    rating_distribution = get_rating_distribution(filters)
    monthly_trend = get_monthly_trend(filters)
    offer_metrics = get_offer_type_metrics(filters)
    left_chart, right_chart = st.columns(2)
    with left_chart:
        st.caption("Distribución de calificaciones")
        if not rating_distribution.empty:
            chart_df = rating_distribution.copy()
            chart_df = chart_df.dropna(subset=["estrellas"])
            if not chart_df.empty:
                chart_df["Etiqueta"] = chart_df["estrellas"].astype(int).astype(str) + " ★"
                st.bar_chart(chart_df.set_index("Etiqueta")["reviews"], color="#f59e0b")
        else:
            st.info("No hay datos de calificación para graficar.")
    with right_chart:
        st.caption("Calificación por tipo de oferta")
        if not offer_metrics.empty:
            st.bar_chart(
                offer_metrics.set_index("tipo_oferta")["promedio_estrellas"],
                color="#14b8a6",
            )
            st.dataframe(
                offer_metrics.rename(columns={
                    "tipo_oferta": "Tipo de oferta", "reviews": "Reviews",
                    "promedio_estrellas": "Promedio", "porcentaje_quejas": "% quejas",
                }), use_container_width=True, hide_index=True,
            )
        else:
            st.info("No hay datos de tipo de oferta.")

    st.caption("Evolución mensual: volumen de reseñas")
    if not monthly_trend.empty:
        timeline = monthly_trend.copy()
        timeline["mes"] = pd.to_datetime(timeline["mes"])
        st.line_chart(
            timeline.set_index("mes")[["reviews", "quejas_criticas"]],
            color=["#38bdf8", "#fb7185"],
        )
        with st.expander("Ver detalle mensual"):
            st.dataframe(
                timeline.rename(columns={
                    "mes": "Mes", "reviews": "Reviews",
                    "promedio_estrellas": "Promedio estrellas",
                    "quejas_criticas": "Quejas críticas",
                }), use_container_width=True, hide_index=True,
            )

    st.markdown('<div class="section-title">🚨 Alertas y publicaciones destacadas</div>',
                unsafe_allow_html=True)
    alerts = get_alerts(filters, limit=MAX_ALERTS, min_reviews=MIN_REVIEWS_FOR_RANKING)
    top_rated = get_top_rated(filters, limit=MAX_ALERTS, min_reviews=MIN_REVIEWS_FOR_RANKING)
    alert_col, top_col = st.columns(2)
    with alert_col:
        st.subheader("🔴 Más quejas críticas")
        st.caption(f"Mínimo {MIN_REVIEWS_FOR_RANKING} reviews por publicación.")
        if alerts.empty:
            st.info("No hay publicaciones suficientes para generar alertas.")
        for _, row in alerts.iterrows():
            product = row["titulo_ecom"]
            if pd.isna(product) or not str(product).strip():
                product = row["sku"]
            st.markdown(
                '<div class="alert-card">'
                f'<strong>{safe_text(row["ml_id"])}</strong><br><small>'
                f'{safe_text(row["cuenta"])} · {safe_text(product, "Producto sin título", 85)}<br>'
                f'<b>{format_number(row["quejas_criticas"])}</b> quejas críticas '
                f'({format_decimal(row["porcentaje_quejas"])}%) · '
                f'Promedio: {format_decimal(row["promedio_estrellas"])} / 5 · '
                f'{format_number(row["total_reviews"])} reviews'
                '</small></div>', unsafe_allow_html=True,
            )
    with top_col:
        st.subheader("🟢 Mejor calificadas")
        st.caption(f"Mínimo {MIN_REVIEWS_FOR_RANKING} reviews por publicación.")
        if top_rated.empty:
            st.info("No hay publicaciones suficientes para generar ranking.")
        for _, row in top_rated.iterrows():
            product = row["titulo_ecom"]
            if pd.isna(product) or not str(product).strip():
                product = row["sku"]
            st.markdown(
                '<div class="top-card">'
                f'<strong>{safe_text(row["ml_id"])}</strong><br><small>'
                f'{safe_text(row["cuenta"])} · {safe_text(product, "Producto sin título", 85)}<br>'
                f'<b>★ {format_decimal(row["promedio_estrellas"])}</b> / 5 · '
                f'{format_number(row["positivas"])} positivas · '
                f'{format_number(row["total_reviews"])} reviews'
                '</small></div>', unsafe_allow_html=True,
            )


def rating_label(value) -> str:
    if value is None or pd.isna(value):
        return "⚪ Sin calificación"
    try:
        rating = int(float(value))
    except (TypeError, ValueError):
        return "⚪ Sin calificación"
    if rating in (1, 2):
        return f"🔴 {rating} ★ · Queja"
    if rating == 3:
        return "🟡 3 ★ · Neutral"
    if rating in (4, 5):
        return f"🟢 {rating} ★ · Positiva"
    return "⚪ Sin calificación"


def render_reviews_table(filters: ReviewFilters) -> None:
    st.markdown('<div class="section-title">🔎 Explorador detallado de reviews</div>',
                unsafe_allow_html=True)
    st.caption("Tabla paginada; los filtros del lateral también se aplican aquí.")
    controls_left, controls_right, _ = st.columns([1, 1, 2])
    with controls_left:
        page_size = st.selectbox(
            "Registros por página", PAGE_SIZE_OPTIONS, index=1, key="reviews_page_size",
        )
    if "reviews_current_page" not in st.session_state:
        st.session_state.reviews_current_page = 1
    reviews, total_rows = get_reviews_page(
        filters, st.session_state.reviews_current_page, page_size,
    )
    total_pages = max(math.ceil(total_rows / page_size), 1)
    if st.session_state.reviews_current_page > total_pages:
        st.session_state.reviews_current_page = total_pages
        st.rerun()
    with controls_right:
        st.metric("Reviews encontradas", format_number(total_rows))
    nav_left, nav_center, nav_right = st.columns([1, 2, 1])
    with nav_left:
        if st.button("← Anterior", disabled=st.session_state.reviews_current_page <= 1,
                     use_container_width=True):
            st.session_state.reviews_current_page -= 1
            st.rerun()
    with nav_center:
        st.markdown(
            f"Página **{st.session_state.reviews_current_page}** de **{total_pages}** "
            f"· Hasta {page_size} registros",
        )
    with nav_right:
        if st.button("Siguiente →",
                     disabled=st.session_state.reviews_current_page >= total_pages,
                     use_container_width=True):
            st.session_state.reviews_current_page += 1
            st.rerun()
    if reviews.empty:
        st.info("No hay reviews para mostrar con los filtros actuales.")
        return
    display = reviews.copy()
    display["calificacion_visual"] = display["estrellas"].apply(rating_label)
    display = display[[
        "ml_id", "cuenta", "fecha_review", "calificacion_visual", "comentario",
        "titulo_review", "estado_meli", "titulo_ecom", "sku", "tipo_publicacion",
        "titulo_meli", "tipo_oferta",
    ]].rename(columns={
        "ml_id": "ML_ID", "cuenta": "Cuenta", "fecha_review": "Fecha review",
        "calificacion_visual": "Calificación", "comentario": "Comentario",
        "titulo_review": "Título review", "estado_meli": "Estado Meli",
        "titulo_ecom": "Título e-commerce", "sku": "SKU",
        "tipo_publicacion": "Tipo publicación", "titulo_meli": "Título Mercado Libre",
        "tipo_oferta": "Tipo oferta",
    })
    st.dataframe(
        display, use_container_width=True, hide_index=True,
        column_config={
            "Fecha review": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
            "Calificación": st.column_config.TextColumn(width="medium"),
            "Comentario": st.column_config.TextColumn(width="large"),
            "Título review": st.column_config.TextColumn(width="medium"),
        },
    )


def run() -> None:
    inject_styles()
    st.markdown(
        '<div class="reviews-hero"><h1>⭐ Reviews Intelligence</h1>'
        '<p>Tablero verificable, alertas de calidad y explorador paginado '
        'de reseñas de Mercado Libre.</p></div>', unsafe_allow_html=True,
    )
    try:
        filters = render_filters()
        render_dashboard(filters)
        render_reviews_table(filters)
    except Exception:
        st.error("No fue posible cargar Reviews Intelligence. Revisa los logs de la aplicación.")
        raise


if __name__ == "__main__":
    run()
