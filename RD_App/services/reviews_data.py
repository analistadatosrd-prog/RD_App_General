from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Iterator

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

TABLE_NAME = "public.rd_tabla_reviews"
AI_REVIEW_COLUMNS = (
    "row_id", "ml_id", "cuenta", "fecha_review", "estrellas",
    "titulo_review", "comentario", "titulo_ecom", "sku",
    "tipo_publicacion", "titulo_meli", "tipo_oferta",
)


@st.cache_resource
def get_reviews_engine():
    database_url = st.secrets.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("Falta DATABASE_URL en Streamlit Secrets.")
    return create_engine(database_url, pool_pre_ping=True)


@dataclass
class ReviewFilters:
    ml_id: str = ""
    cuenta: list[str] = field(default_factory=list)
    fecha_desde: date | None = None
    fecha_hasta: date | None = None
    estrellas: list[int] = field(default_factory=list)
    estado_meli: list[str] = field(default_factory=list)
    titulo_ecom: str = ""
    sku: str = ""
    tipo_publicacion: list[str] = field(default_factory=list)
    titulo_meli: str = ""
    tipo_oferta: list[str] = field(default_factory=list)


def _clean_text(value: str | None) -> str:
    return (value or "").strip()


def build_where_clause(filters: ReviewFilters) -> tuple[str, dict[str, Any]]:
    conditions: list[str] = []
    params: dict[str, Any] = {}

    for column in ("ml_id", "titulo_ecom", "sku", "titulo_meli"):
        value = _clean_text(getattr(filters, column))
        if value:
            conditions.append(f"{column} ILIKE :{column}")
            params[column] = f"%{value}%"

    for column in ("cuenta", "estrellas", "estado_meli", "tipo_publicacion", "tipo_oferta"):
        values = getattr(filters, column)
        if values:
            conditions.append(f"{column} = ANY(:{column})")
            params[column] = values

    if filters.fecha_desde:
        conditions.append("fecha_review >= :fecha_desde")
        params["fecha_desde"] = datetime.combine(filters.fecha_desde, time.min)

    if filters.fecha_hasta:
        conditions.append("fecha_review < :fecha_hasta")
        params["fecha_hasta"] = datetime.combine(
            filters.fecha_hasta + timedelta(days=1), time.min
        )

    return " AND ".join(conditions) if conditions else "TRUE", params


@st.cache_data(ttl=900)
def get_filter_options() -> dict[str, list[str]]:
    query = text(f"""
        SELECT
            ARRAY(
                SELECT DISTINCT cuenta FROM {TABLE_NAME}
                WHERE cuenta IS NOT NULL AND BTRIM(cuenta) <> '' ORDER BY cuenta
            ) AS cuentas,
            ARRAY(
                SELECT DISTINCT estado_meli FROM {TABLE_NAME}
                WHERE estado_meli IS NOT NULL AND BTRIM(estado_meli) <> '' ORDER BY estado_meli
            ) AS estados_meli,
            ARRAY(
                SELECT DISTINCT tipo_publicacion FROM {TABLE_NAME}
                WHERE tipo_publicacion IS NOT NULL AND BTRIM(tipo_publicacion) <> ''
                ORDER BY tipo_publicacion
            ) AS tipos_publicacion,
            ARRAY(
                SELECT DISTINCT tipo_oferta FROM {TABLE_NAME}
                WHERE tipo_oferta IS NOT NULL AND BTRIM(tipo_oferta) <> '' ORDER BY tipo_oferta
            ) AS tipos_oferta
    """)
    with get_reviews_engine().connect() as connection:
        row = connection.execute(query).mappings().one()
    return {
        "cuentas": list(row["cuentas"] or []),
        "estados_meli": list(row["estados_meli"] or []),
        "tipos_publicacion": list(row["tipos_publicacion"] or []),
        "tipos_oferta": list(row["tipos_oferta"] or []),
    }


def get_date_bounds() -> tuple[date, date]:
    query = text(f"""
        SELECT MIN(fecha_review)::date AS fecha_minima,
               MAX(fecha_review)::date AS fecha_maxima
        FROM {TABLE_NAME}
    """)
    with get_reviews_engine().connect() as connection:
        row = connection.execute(query).mappings().one()
    if not row["fecha_minima"] or not row["fecha_maxima"]:
        raise RuntimeError("No se encontraron fechas válidas en rd_tabla_reviews.")
    return row["fecha_minima"], row["fecha_maxima"]


def get_dashboard_metrics(filters: ReviewFilters) -> dict[str, Any]:
    where_sql, params = build_where_clause(filters)
    query = text(f"""
        SELECT COUNT(*) AS total_reviews,
               COUNT(DISTINCT ml_id) AS publicaciones_unicas,
               COUNT(DISTINCT sku) AS skus_unicos,
               ROUND(AVG(estrellas)::numeric, 2) AS promedio_estrellas,
               COUNT(*) FILTER (WHERE estrellas IN (1, 2)) AS quejas_criticas,
               ROUND(100.0 * COUNT(*) FILTER (WHERE estrellas IN (1, 2))
                   / NULLIF(COUNT(*), 0), 2) AS porcentaje_quejas_criticas,
               COUNT(*) FILTER (WHERE estrellas IN (4, 5)) AS positivas,
               ROUND(100.0 * COUNT(*) FILTER (WHERE estrellas IN (4, 5))
                   / NULLIF(COUNT(*), 0), 2) AS porcentaje_satisfaccion
        FROM {TABLE_NAME}
        WHERE {where_sql}
    """)
    with get_reviews_engine().connect() as connection:
        return dict(connection.execute(query, params).mappings().one())


def get_rating_distribution(filters: ReviewFilters) -> pd.DataFrame:
    where_sql, params = build_where_clause(filters)
    query = text(f"""
        SELECT estrellas, COUNT(*) AS reviews FROM {TABLE_NAME}
        WHERE {where_sql} GROUP BY estrellas ORDER BY estrellas DESC
    """)
    with get_reviews_engine().connect() as connection:
        return pd.read_sql(query, connection, params=params)


def get_monthly_trend(filters: ReviewFilters) -> pd.DataFrame:
    where_sql, params = build_where_clause(filters)
    query = text(f"""
        SELECT DATE_TRUNC('month', fecha_review)::date AS mes,
               COUNT(*) AS reviews,
               ROUND(AVG(estrellas)::numeric, 2) AS promedio_estrellas,
               COUNT(*) FILTER (WHERE estrellas IN (1, 2)) AS quejas_criticas
        FROM {TABLE_NAME} WHERE {where_sql} GROUP BY 1 ORDER BY 1
    """)
    with get_reviews_engine().connect() as connection:
        return pd.read_sql(query, connection, params=params)


def get_offer_type_metrics(filters: ReviewFilters) -> pd.DataFrame:
    where_sql, params = build_where_clause(filters)
    query = text(f"""
        SELECT COALESCE(NULLIF(BTRIM(tipo_oferta), ''), 'Sin clasificación') AS tipo_oferta,
               COUNT(*) AS reviews,
               ROUND(AVG(estrellas)::numeric, 2) AS promedio_estrellas,
               ROUND(100.0 * COUNT(*) FILTER (WHERE estrellas IN (1, 2))
                   / NULLIF(COUNT(*), 0), 2) AS porcentaje_quejas
        FROM {TABLE_NAME} WHERE {where_sql} GROUP BY 1 ORDER BY reviews DESC
    """)
    with get_reviews_engine().connect() as connection:
        return pd.read_sql(query, connection, params=params)


def get_alerts(
    filters: ReviewFilters, limit: int = 10, min_reviews: int = 5
) -> pd.DataFrame:
    where_sql, params = build_where_clause(filters)
    params.update({"limit": limit, "min_reviews": min_reviews})
    query = text(f"""
        SELECT ml_id, MAX(cuenta) AS cuenta, MAX(titulo_ecom) AS titulo_ecom,
               MAX(sku) AS sku, MAX(tipo_oferta) AS tipo_oferta,
               COUNT(*) AS total_reviews,
               COUNT(*) FILTER (WHERE estrellas IN (1, 2)) AS quejas_criticas,
               ROUND(100.0 * COUNT(*) FILTER (WHERE estrellas IN (1, 2))
                   / NULLIF(COUNT(*), 0), 2) AS porcentaje_quejas,
               ROUND(AVG(estrellas)::numeric, 2) AS promedio_estrellas
        FROM {TABLE_NAME} WHERE {where_sql} GROUP BY ml_id
        HAVING COUNT(*) >= :min_reviews
        ORDER BY quejas_criticas DESC, porcentaje_quejas DESC,
                 total_reviews DESC, ml_id LIMIT :limit
    """)
    with get_reviews_engine().connect() as connection:
        return pd.read_sql(query, connection, params=params)


def get_top_rated(
    filters: ReviewFilters, limit: int = 10, min_reviews: int = 5
) -> pd.DataFrame:
    where_sql, params = build_where_clause(filters)
    params.update({"limit": limit, "min_reviews": min_reviews})
    query = text(f"""
        SELECT ml_id, MAX(cuenta) AS cuenta, MAX(titulo_ecom) AS titulo_ecom,
               MAX(sku) AS sku, MAX(tipo_oferta) AS tipo_oferta,
               COUNT(*) AS total_reviews,
               ROUND(AVG(estrellas)::numeric, 2) AS promedio_estrellas,
               COUNT(*) FILTER (WHERE estrellas IN (4, 5)) AS positivas
        FROM {TABLE_NAME} WHERE {where_sql} GROUP BY ml_id
        HAVING COUNT(*) >= :min_reviews
        ORDER BY promedio_estrellas DESC, total_reviews DESC, ml_id LIMIT :limit
    """)
    with get_reviews_engine().connect() as connection:
        return pd.read_sql(query, connection, params=params)


def get_reviews_page(
    filters: ReviewFilters, page: int, page_size: int
) -> tuple[pd.DataFrame, int]:
    where_sql, params = build_where_clause(filters)
    safe_page = max(int(page), 1)
    safe_page_size = min(max(int(page_size), 25), 100)
    params.update({"limit": safe_page_size, "offset": (safe_page - 1) * safe_page_size})
    count_query = text(f"SELECT COUNT(*) AS total FROM {TABLE_NAME} WHERE {where_sql}")
    page_query = text(f"""
        SELECT row_id, ml_id, cuenta, fecha_review, estrellas, estado_meli,
               titulo_ecom, sku, tipo_publicacion, titulo_meli, tipo_oferta,
               titulo_review, comentario
        FROM {TABLE_NAME} WHERE {where_sql}
        ORDER BY fecha_review DESC, row_id ASC LIMIT :limit OFFSET :offset
    """)
    with get_reviews_engine().connect() as connection:
        total = connection.execute(count_query, params).scalar_one()
        reviews = pd.read_sql(page_query, connection, params=params)
    return reviews, int(total)


def _ai_text_condition() -> str:
    return "(NULLIF(BTRIM(titulo_review), '') IS NOT NULL OR NULLIF(BTRIM(comentario), '') IS NOT NULL)"


def _ai_evidence_where(filters: ReviewFilters) -> tuple[str, dict[str, Any]]:
    where_sql, params = build_where_clause(filters)
    return f"({where_sql}) AND {_ai_text_condition()}", params


def get_ai_context_metrics(filters: ReviewFilters) -> dict[str, Any]:
    """Métricas SQL exactas del universo filtrado; sin llamadas a IA ni cache."""
    where_sql, params = build_where_clause(filters)
    query = text(f"""
        SELECT COUNT(*) AS total_reviews,
               COUNT(*) FILTER (WHERE {_ai_text_condition()}) AS reviews_con_texto,
               COUNT(DISTINCT ml_id) AS publicaciones_unicas,
               COUNT(DISTINCT sku) AS skus_unicos,
               ROUND(AVG(estrellas)::numeric, 2) AS promedio_estrellas,
               COUNT(*) FILTER (WHERE estrellas = 1) AS estrellas_1,
               COUNT(*) FILTER (WHERE estrellas = 2) AS estrellas_2,
               COUNT(*) FILTER (WHERE estrellas = 3) AS estrellas_3,
               COUNT(*) FILTER (WHERE estrellas = 4) AS estrellas_4,
               COUNT(*) FILTER (WHERE estrellas = 5) AS estrellas_5,
               COUNT(*) FILTER (WHERE estrellas IN (1, 2)) AS quejas_criticas,
               COUNT(*) FILTER (WHERE estrellas IN (4, 5)) AS positivas,
               MIN(fecha_review) AS primera_fecha,
               MAX(fecha_review) AS ultima_fecha
        FROM {TABLE_NAME} WHERE {where_sql}
    """)
    with get_reviews_engine().connect() as connection:
        return dict(connection.execute(query, params).mappings().one())


def count_ai_evidence_reviews(filters: ReviewFilters) -> int:
    """Cuenta exactamente las filas con título o comentario disponibles para análisis."""
    where_sql, params = _ai_evidence_where(filters)
    query = text(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE {where_sql}")
    with get_reviews_engine().connect() as connection:
        return int(connection.execute(query, params).scalar_one())


def iter_ai_review_batches(
    filters: ReviewFilters, batch_size: int = 200
) -> Iterator[list[dict[str, Any]]]:
    """Lee toda la evidencia filtrada en lotes, sin muestreo ni escrituras.

    Mantén el generador abierto mientras consumes cada lote. Para consultas largas,
    las inserciones posteriores al inicio de la lectura no forman parte del cursor;
    calcula la cobertura a partir de las filas realmente recorridas.
    """
    safe_batch_size = int(batch_size)
    if not 1 <= safe_batch_size <= 1_000:
        raise ValueError("batch_size debe estar entre 1 y 1000.")
    where_sql, params = _ai_evidence_where(filters)
    query = text(f"""
        SELECT {', '.join(AI_REVIEW_COLUMNS)}
        FROM {TABLE_NAME}
        WHERE {where_sql}
        ORDER BY row_id ASC
    """)
    with get_reviews_engine().connect() as connection:
        streaming = connection.execution_options(yield_per=safe_batch_size)
        result = streaming.execute(query, params).mappings()
        try:
            while True:
                rows = result.fetchmany(safe_batch_size)
                if not rows:
                    break
                yield [dict(row) for row in rows]
        finally:
            result.close()
