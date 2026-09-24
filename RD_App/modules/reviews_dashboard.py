from __future__ import annotations

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
    if value is None:
        return "0"

    return f"{int(value):,}".replace(",", ".")


def format_decimal(value, digits: int = 2) -> str:
    if value is None:
        return "N/D"

    return f"{float(value):.{digits}f}".replace(".", ",")


def get_default_date_range(
    date_min: date,
    date_max: date,
) -> tuple[date, date]:
    return date_min, date_max


def inject_styles() -> None:
    st.markdown(
        """
        <style>
            .reviews-hero {
                padding: 1.4rem 1.6rem;
                border-radius: 18px;
                margin: 0 0 1rem 0;
                background: linear-gradient(
                    135deg,
                    #0f172a 0%,
                    #172554 55%,
                    #0f766e 120%
                );
                border: 1px solid #334155;
            }

            .reviews-hero h1 {
                color: #f8fafc;
                font-size: 1.7rem;
                margin: 0;
            }

            .reviews-hero p {
                color: #cbd5e1;
                margin: 0.35rem 0 0 0;
            }

            .metric-card {
                border-radius: 16px;
                padding: 1.05rem 1.15rem;
                min-height: 132px;
                border: 1px solid #26354f;
                background: #101b31;
                margin-bottom: 0.5rem;
            }

            .metric-card .metric-label {
                color: #94a3b8;
                font-size: 0.76rem;
                text-transform: uppercase;
                letter-spacing: 0.04em;
                font-weight: 700;
            }

            .metric-card .metric-value {
                color: #f8fafc;
                font-size: 2rem;
                line-height: 1.25;
                font-weight: 800;
                margin: 0.35rem 0 0.15rem 0;
            }

            .metric-card .metric-caption {
                color: #cbd5e1;
                font-size: 0.8rem;
            }

            .metric-card.green {
                border-left: 5px solid #10b981;
            }

            .metric-card.blue {
                border-left: 5px solid #38bdf8;
            }

            .metric-card.amber {
                border-left: 5px solid #f59e0b;
            }

            .metric-card.red {
                border-left: 5px solid #fb7185;
            }

            .alert-card {
                padding: 0.85rem 1rem;
                border-radius: 12px;
                background: #21172a;
                border: 1px solid #5a2845;
                margin: 0.5rem 0;
            }

            .alert-card strong {
                color: #fda4af;
            }

            .alert-card small {
                color: #cbd5e1;
            }

            .top-card {
                padding: 0.85rem 1rem;
                border-radius: 12px;
                background: #0d2929;
                border: 1px solid #145f5a;
                margin: 0.5rem 0;
            }

            .top-card strong {
                color: #5eead4;
            }

            .top-card small {
                color: #cbd5e1;
            }

            .filter-summary {
                padding: 0.75rem 1rem;
                border-radius: 10px;
                color: #dbeafe;
                background: #14213d;
                border: 1px solid #254878;
                margin: 0.6rem 0 1rem 0;
                font-size: 0.9rem;
            }

            .section-title {
                margin-top: 1.4rem;
                color: #f8fafc;
                font-weight: 800;
                font-size: 1.15rem;
            }

            [data-testid="stSidebar"] .reviews-filter-panel {
                padding: 0.9rem;
                border-radius: 14px;
                background: linear-gradient(
                    145deg,
                    #0f2d52 0%,
                    #123e72 100%
                );
                border: 1px solid #2d6db1;
                margin: 0.65rem 0 1rem 0;
            }

            [data-testid="stSidebar"] .reviews-filter-panel h3 {
                margin: 0;
                color: #f8fafc;
                font-size: 1rem;
            }

            [data-testid="stSidebar"] .reviews-filter-panel p {
                color: #bfdbfe;
                font-size: 0.76rem;
                line-height: 1.35;
                margin: 0.35rem 0 0 0;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(
    label: str,
    value: str,
    caption: str,
    color_class: str,
) -> None:
    st.markdown(
        f"""
        <div class="metric-card {color_class}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-caption">{caption}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_filters() -> ReviewFilters:
    """
    Los filtros viven en la barra lateral de Streamlit, que permanece
    fija durante el scroll y aplica el mismo universo a tablero,
    alertas y explorador.
    """
    options = get_filter_options()
    date_min, date_max = get_date_bounds()

    if "reviews_date_range" not in st.session_state:
        st.session_state.reviews_date_range = (
            get_default_date_range(date_min, date_max)
        )

    with st.sidebar:
        st.markdown(
            """
            <div class="reviews-filter-panel">
                <h3>🎛️ Filtros de Reviews</h3>
                <p>
                    Aplican a todo Reviews Intelligence:
                    tablero, alertas y explorador.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        quick_range = st.selectbox(
            "Período",
            options=[
                "Todo el historial",
                "Últimos 7 días",
                "Últimos 30 días",
                "Últimos 90 días",
                "Año actual",
                "Rango personalizado",
            ],
            key="reviews_quick_range",
        )

        today = date_max

        if quick_range == "Todo el historial":
            selected_range = (date_min, date_max)

        elif quick_range == "Últimos 7 días":
            selected_range = (
                max(date_min, today - timedelta(days=6)),
                date_max,
            )

        elif quick_range == "Últimos 30 días":
            selected_range = (
                max(date_min, today - timedelta(days=29)),
                date_max,
            )

        elif quick_range == "Últimos 90 días":
            selected_range = (
                max(date_min, today - timedelta(days=89)),
                date_max,
            )

        elif quick_range == "Año actual":
            year_start = date(today.year, 1, 1)
            selected_range = (
                max(date_min, year_start),
                date_max,
            )

        else:
            selected_range = st.date_input(
                "Rango de fechas",
                value=st.session_state.reviews_date_range,
                min_value=date_min,
                max_value=date_max,
                key="reviews_custom_date_range",
            )

            if isinstance(selected_range, date):
                selected_range = (
                    selected_range,
                    selected_range,
                )

            if len(selected_range) != 2:
                selected_range = st.session_state.reviews_date_range

        st.session_state.reviews_date_range = selected_range

        with st.expander(
            "Identificación y producto",
            expanded=True,
        ):
            ml_id = st.text_input(
                "ML_ID",
                placeholder="Ej. MLA123456789",
                key="reviews_ml_id",
            )

            sku = st.text_input(
                "SKU",
                placeholder="Buscar SKU",
                key="reviews_sku",
            )

            titulo_ecom = st.text_input(
                "Título e-commerce",
                placeholder="Buscar producto asociado",
                key="reviews_titulo_ecom",
            )

            titulo_meli = st.text_input(
                "Título Mercado Libre",
                placeholder="Buscar publicación",
                key="reviews_titulo_meli",
            )

        with st.expander(
            "Cuenta y publicación",
            expanded=False,
        ):
            cuenta = st.multiselect(
                "Cuenta",
                options=options["cuentas"],
                key="reviews_cuenta",
            )

            estado_meli = st.multiselect(
                "Estado Mercado Libre",
                options=options["estados_meli"],
                key="reviews_estado_meli",
            )

            tipo_publicacion = st.multiselect(
                "Tipo de publicación",
                options=options["tipos_publicacion"],
                key="reviews_tipo_publicacion",
            )

            tipo_oferta = st.multiselect(
                "Tipo de oferta",
                options=options["tipos_oferta"],
                key="reviews_tipo_oferta",
            )

        with st.expander(
            "Calificación",
            expanded=False,
        ):
            estrellas = st.multiselect(
                "Estrellas",
                options=[1, 2, 3, 4, 5],
                format_func=lambda value: f"{value} estrella(s)",
                key="reviews_estrellas",
            )

        if st.button(
            "↻ Restablecer filtros",
            use_container_width=True,
            type="secondary",
        ):
            keys_to_reset = [
                "reviews_quick_range",
                "reviews_custom_date_range",
                "reviews_ml_id",
                "reviews_cuenta",
                "reviews_estrellas",
                "reviews_estado_meli",
                "reviews_titulo_ecom",
                "reviews_sku",
                "reviews_tipo_publicacion",
                "reviews_tipo_oferta",
                "reviews_titulo_meli",
                "reviews_current_page",
            ]

            for key in keys_to_reset:
                st.session_state.pop(key, None)

            st.session_state.reviews_date_range = (
                get_default_date_range(date_min, date_max)
            )
            st.rerun()

    return ReviewFilters(
        ml_id=ml_id,
        cuenta=cuenta,
        fecha_desde=selected_range[0],
        fecha_hasta=selected_range[1],
        estrellas=estrellas,
        estado_meli=estado_meli,
        titulo_ecom=titulo_ecom,
        sku=sku,
        tipo_publicacion=tipo_publicacion,
        titulo_meli=titulo_meli,
        tipo_oferta=tipo_oferta,
    )


def build_filter_summary(filters: ReviewFilters) -> str:
    parts = [
        (
            f"📅 {filters.fecha_desde:%d/%m/%Y}"
            f"–{filters.fecha_hasta:%d/%m/%Y}"
        )
    ]

    if filters.ml_id:
        parts.append(f"ML_ID contiene: {filters.ml_id}")

    if filters.cuenta:
        parts.append(f"Cuenta: {', '.join(filters.cuenta)}")

    if filters.estrellas:
        parts.append(
            "Estrellas: " + ", ".join(map(str, filters.estrellas))
        )

    if filters.estado_meli:
        parts.append(
            "Estado: " + ", ".join(filters.estado_meli)
        )

    if filters.titulo_ecom:
        parts.append(
            f"Título e-commerce: {filters.titulo_ecom}"
        )

    if filters.sku:
        parts.append(f"SKU contiene: {filters.sku}")

    if filters.tipo_publicacion:
        parts.append(
            "Publicación: "
            + ", ".join(filters.tipo_publicacion)
        )

    if filters.titulo_meli:
        parts.append(
            f"Título Mercado Libre: {filters.titulo_meli}"
        )

    if filters.tipo_oferta:
        parts.append(
            "Oferta: " + ", ".join(filters.tipo_oferta)
        )

    return " &nbsp; • &nbsp; ".join(parts)


def render_dashboard(
    filters: ReviewFilters,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    metrics = get_dashboard_metrics(filters)

    st.markdown(
        f"""
        <div class="filter-summary">
            <strong>Universo activo:</strong>
            {build_filter_summary(filters)}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="section-title">📊 Resumen del universo filtrado</div>',
        unsafe_allow_html=True,
    )

    col_1, col_2, col_3, col_4 = st.columns(4)

    with col_1:
        render_metric_card(
            "Reviews analizadas",
            format_number(metrics["total_reviews"]),
            (
                f"{format_number(metrics['publicaciones_unicas'])} "
                "publicaciones únicas"
            ),
            "blue",
        )

    with col_2:
        render_metric_card(
            "Calificación promedio",
            f"{format_decimal(metrics['promedio_estrellas'])} / 5",
            (
                f"{format_number(metrics['skus_unicos'])} "
                "SKU asociados"
            ),
            "amber",
        )

    with col_3:
        render_metric_card(
            "Satisfacción (4–5★)",
            f"{format_decimal(metrics['porcentaje_satisfaccion'])}%",
            (
                f"{format_number(metrics['positivas'])} "
                "reviews positivas"
            ),
            "green",
        )

    with col_4:
        render_metric_card(
            "Quejas críticas (1–2★)",
            f"{format_decimal(metrics['porcentaje_quejas_criticas'])}%",
            (
                f"{format_number(metrics['quejas_criticas'])} "
                "reviews críticas"
            ),
            "red",
        )

    if not metrics["total_reviews"]:
        st.warning(
            "No se encontraron reviews con los filtros seleccionados."
        )
        return pd.DataFrame(), pd.DataFrame()

    st.markdown(
        '<div class="section-title">📈 Comportamiento de calificaciones</div>',
        unsafe_allow_html=True,
    )

    left_chart, right_chart = st.columns(2)

    rating_distribution = get_rating_distribution(filters)
    monthly_trend = get_monthly_trend(filters)
    offer_metrics = get_offer_type_metrics(filters)

    with left_chart:
        st.caption("Distribución de calificaciones")

        if rating_distribution.empty:
            st.info("No hay datos de calificación para graficar.")
        else:
            chart_df = rating_distribution.copy()
            chart_df["Etiqueta"] = (
                chart_df["estrellas"].astype(int).astype(str) + " ★"
            )

            st.bar_chart(
                chart_df.set_index("Etiqueta")["reviews"],
                color="#f59e0b",
                use_container_width=True,
            )

    with right_chart:
        st.caption("Calificación por tipo de oferta")

        if offer_metrics.empty:
            st.info("No hay datos de tipo de oferta.")
        else:
            chart_df = offer_metrics.set_index("tipo_oferta")

            st.bar_chart(
                chart_df["promedio_estrellas"],
                color="#14b8a6",
                use_container_width=True,
            )

            st.dataframe(
                offer_metrics.rename(
                    columns={
                        "tipo_oferta": "Tipo de oferta",
                        "reviews": "Reviews",
                        "promedio_estrellas": "Promedio",
                        "porcentaje_quejas": "% quejas",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

    st.caption("Evolución mensual: volumen de reseñas")

    if not monthly_trend.empty:
        timeline = monthly_trend.copy()
        timeline["mes"] = pd.to_datetime(timeline["mes"])

        st.line_chart(
            timeline.set_index("mes")[
                ["reviews", "quejas_criticas"]
            ],
            color=["#38bdf8", "#fb7185"],
            use_container_width=True,
        )

        with st.expander("Ver detalle mensual"):
            monthly_display = timeline.rename(
                columns={
                    "mes": "Mes",
                    "reviews": "Reviews",
                    "promedio_estrellas": "Promedio estrellas",
                    "quejas_criticas": "Quejas críticas",
                }
            )

            st.dataframe(
                monthly_display,
                use_container_width=True,
                hide_index=True,
            )

    st.markdown(
        '<div class="section-title">🚨 Alertas y publicaciones destacadas</div>',
        unsafe_allow_html=True,
    )

    alerts = get_alerts(
        filters,
        limit=MAX_ALERTS,
        min_reviews=MIN_REVIEWS_FOR_RANKING,
    )

    top_rated = get_top_rated(
        filters,
        limit=MAX_ALERTS,
        min_reviews=MIN_REVIEWS_FOR_RANKING,
    )

    alert_col, top_col = st.columns(2)

    with alert_col:
        st.subheader("🔴 Más quejas críticas")
        st.caption(
            f"Mínimo {MIN_REVIEWS_FOR_RANKING} reviews por publicación."
        )

        if alerts.empty:
            st.info(
                "No hay publicaciones suficientes para generar alertas."
            )
        else:
            for _, row in alerts.iterrows():
                product_name = (
                    row["titulo_ecom"]
                    or row["sku"]
                    or "Producto sin título"
                )

                st.markdown(
                    f"""
                    <div class="alert-card">
                        <strong>{row["ml_id"]}</strong><br>
                        <small>
                            {row["cuenta"] or "Sin cuenta"} ·
                            {str(product_name)[:85]}<br>
                            <b>{format_number(row["quejas_criticas"])}</b>
                            quejas críticas
                            ({format_decimal(row["porcentaje_quejas"])}%) ·
                            Promedio:
                            {format_decimal(row["promedio_estrellas"])} / 5 ·
                            {format_number(row["total_reviews"])} reviews
                        </small>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with top_col:
        st.subheader("🟢 Mejor calificadas")
        st.caption(
            f"Mínimo {MIN_REVIEWS_FOR_RANKING} reviews por publicación."
        )

        if top_rated.empty:
            st.info(
                "No hay publicaciones suficientes para generar ranking."
            )
        else:
            for _, row in top_rated.iterrows():
                product_name = (
                    row["titulo_ecom"]
                    or row["sku"]
                    or "Producto sin título"
                )

                st.markdown(
                    f"""
                    <div class="top-card">
                        <strong>{row["ml_id"]}</strong><br>
                        <small>
                            {row["cuenta"] or "Sin cuenta"} ·
                            {str(product_name)[:85]}<br>
                            <b>★ {format_decimal(row["promedio_estrellas"])}</b>
                            / 5 ·
                            {format_number(row["positivas"])} positivas ·
                            {format_number(row["total_reviews"])} reviews
                        </small>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    return alerts, top_rated


def rating_label(value) -> str:
    try:
        rating = int(float(value))
    except (TypeError, ValueError):
        return "⚪ Sin calificación"

    if rating in (1, 2):
        return f"🔴 {rating} ★ · Queja"

    if rating == 3:
        return "🟡 3 ★ · Neutral"

    return f"🟢 {rating} ★ · Positiva"


def render_reviews_table(filters: ReviewFilters) -> None:
    st.markdown(
        '<div class="section-title">🔎 Explorador detallado de reviews</div>',
        unsafe_allow_html=True,
    )

    st.caption(
        "La tabla se pagina para proteger rendimiento. Los filtros "
        "fijos del lateral se aplican también aquí."
    )

    controls_left, controls_right, _ = st.columns([1, 1, 2])

    with controls_left:
        page_size = st.selectbox(
            "Registros por página",
            options=PAGE_SIZE_OPTIONS,
            index=1,
            key="reviews_page_size",
        )

    if "reviews_current_page" not in st.session_state:
        st.session_state.reviews_current_page = 1

    reviews, total_rows = get_reviews_page(
        filters=filters,
        page=st.session_state.reviews_current_page,
        page_size=page_size,
    )

    total_pages = max(math.ceil(total_rows / page_size), 1)

    if st.session_state.reviews_current_page > total_pages:
        st.session_state.reviews_current_page = total_pages
        st.rerun()

    with controls_right:
        st.metric(
            "Reviews encontradas",
            format_number(total_rows),
            help="Total de filas que cumplen los filtros activos.",
        )

    nav_left, nav_center, nav_right = st.columns([1, 2, 1])

    with nav_left:
        if st.button(
            "← Anterior",
            disabled=st.session_state.reviews_current_page <= 1,
            use_container_width=True,
        ):
            st.session_state.reviews_current_page -= 1
            st.rerun()

    with nav_center:
        st.markdown(
            (
                "<div style='text-align:center; padding:0.45rem;'>"
                f"Página <b>{st.session_state.reviews_current_page}</b> "
                f"de <b>{total_pages}</b> · "
                f"Mostrando hasta {page_size} registros"
                "</div>"
            ),
            unsafe_allow_html=True,
        )

    with nav_right:
        if st.button(
            "Siguiente →",
            disabled=(
                st.session_state.reviews_current_page >= total_pages
            ),
            use_container_width=True,
        ):
            st.session_state.reviews_current_page += 1
            st.rerun()

    if reviews.empty:
        st.info(
            "No hay reviews para mostrar con los filtros actuales."
        )
        return

    compact_reviews = reviews.copy()

    compact_reviews["comentario"] = (
        compact_reviews["comentario"]
        .fillna("")
        .astype(str)
        .str.replace(r"\s+", " ", regex=True)
        .str.slice(0, 240)
    )

    compact_reviews["calificacion_visual"] = (
        compact_reviews["estrellas"].apply(rating_label)
    )

    table_columns = [
        "ml_id",
        "cuenta",
        "fecha_review",
        "calificacion_visual",
        "comentario",
        "titulo_review",
        "estado_meli",
        "titulo_ecom",
        "sku",
        "tipo_publicacion",
        "titulo_meli",
        "tipo_oferta",
    ]

    compact_reviews = compact_reviews[table_columns].rename(
        columns={
            "ml_id": "ML_ID",
            "cuenta": "Cuenta",
            "fecha_review": "Fecha review",
            "calificacion_visual": "Calificación",
            "comentario": "Comentario",
            "titulo_review": "Título review",
            "estado_meli": "Estado Meli",
            "titulo_ecom": "Título e-commerce",
            "sku": "SKU",
            "tipo_publicacion": "Tipo publicación",
            "titulo_meli": "Título Mercado Libre",
            "tipo_oferta": "Tipo oferta",
        }
    )

    st.dataframe(
        compact_reviews,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Fecha review": st.column_config.DatetimeColumn(
                format="DD/MM/YYYY HH:mm",
            ),
            "Calificación": st.column_config.TextColumn(
                width="medium",
            ),
            "Comentario": st.column_config.TextColumn(
                width="large",
            ),
            "Título review": st.column_config.TextColumn(
                width="medium",
            ),
        },
    )


def run():
    st.set_page_config(
        page_title="Reviews Intelligence",
        page_icon="⭐",
        layout="wide",
    )

    inject_styles()

    st.markdown(
        """
        <div class="reviews-hero">
            <h1>⭐ Reviews Intelligence</h1>
            <p>
                Tablero verificable, alertas de calidad y explorador
                paginado de reseñas de Mercado Libre.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        filters = render_filters()
        render_dashboard(filters)
        render_reviews_table(filters)

    except Exception as exc:
        st.error(
            "No fue posible cargar el módulo de Reviews Intelligence."
        )
        st.exception(exc)


if __name__ == "__main__":
    run()
