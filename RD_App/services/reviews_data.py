from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text


TABLE_NAME = "public.rd_tabla_reviews"


@st.cache_resource
def get_reviews_engine():
    database_url = st.secrets.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "Falta DATABASE_URL en Streamlit Secrets."
        )

    return create_engine(
        database_url,
        pool_pre_ping=True,
    )


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
    """
    Construye el mismo WHERE parametrizado para tablero, tabla e IA.
    No inserta texto del usuario directamente dentro del SQL.
    """
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if _clean_text(filters.ml_id):
        conditions.append("ml_id ILIKE :ml_id")
        params["ml_id"] = f"%{_clean_text(filters.ml_id)}%"

    if filters.cuenta:
        conditions.append("cuenta = ANY(:cuenta)")
        params["cuenta"] = filters.cuenta

    if filters.fecha_desde:
        conditions.append("fecha_review >= :fecha_desde")
        params["fecha_desde"] = datetime.combine(
            filters.fecha_desde,
            time.min,
        )

    if filters.fecha_hasta:
        conditions.append("fecha_review < :fecha_hasta")
        params["fecha_hasta"] = datetime.combine(
            filters.fecha_hasta + timedelta(days=1),
            time.min,
        )

    if filters.estrellas:
        conditions.append("estrellas = ANY(:estrellas)")
        params["estrellas"] = filters.estrellas

    if filters.estado_meli:
        conditions.append("estado_meli = ANY(:estado_meli)")
        params["estado_meli"] = filters.estado_meli

    if _clean_text(filters.titulo_ecom):
        conditions.append("titulo_ecom ILIKE :titulo_ecom")
        params["titulo_ecom"] = (
            f"%{_clean_text(filters.titulo_ecom)}%"
        )

    if _clean_text(filters.sku):
        conditions.append("sku ILIKE :sku")
        params["sku"] = f"%{_clean_text(filters.sku)}%"

    if filters.tipo_publicacion:
        conditions.append(
            "tipo_publicacion = ANY(:tipo_publicacion)"
        )
        params["tipo_publicacion"] = filters.tipo_publicacion

    if _clean_text(filters.titulo_meli):
        conditions.append("titulo_meli ILIKE :titulo_meli")
        params["titulo_meli"] = (
            f"%{_clean_text(filters.titulo_meli)}%"
        )

    if filters.tipo_oferta:
        conditions.append("tipo_oferta = ANY(:tipo_oferta)")
        params["tipo_oferta"] = filters.tipo_oferta

    where_sql = " AND ".join(conditions) if conditions else "TRUE"

    return where_sql, params


@st.cache_data(ttl=900)
def get_filter_options() -> dict[str, list[str]]:
    """
    Opciones para filtros de lista. Cache de 15 minutos para evitar
    SELECT DISTINCT repetidos en cada interacción.
    """
    query = text(f"""
        SELECT
            ARRAY(
                SELECT DISTINCT cuenta
                FROM {TABLE_NAME}
                WHERE cuenta IS NOT NULL
                  AND BTRIM(cuenta) <> ''
                ORDER BY cuenta
            ) AS cuentas,
            ARRAY(
                SELECT DISTINCT estado_meli
                FROM {TABLE_NAME}
                WHERE estado_meli IS NOT NULL
                  AND BTRIM(estado_meli) <> ''
                ORDER BY estado_meli
            ) AS estados_meli,
            ARRAY(
                SELECT DISTINCT tipo_publicacion
                FROM {TABLE_NAME}
                WHERE tipo_publicacion IS NOT NULL
                  AND BTRIM(tipo_publicacion) <> ''
                ORDER BY tipo_publicacion
            ) AS tipos_publicacion,
            ARRAY(
                SELECT DISTINCT tipo_oferta
                FROM {TABLE_NAME}
                WHERE tipo_oferta IS NOT NULL
                  AND BTRIM(tipo_oferta) <> ''
                ORDER BY tipo_oferta
            ) AS tipos_oferta
    """)

    with get_reviews_engine().connect() as connection:
        row = connection.execute(query).mappings().one()

    return {
        "cuentas": list(row["cuentas"] or []),
        "estados_meli": list(row["estados_meli"] or []),
        "tipos_publicacion": list(
            row["tipos_publicacion"] or []
        ),
        "tipos_oferta": list(row["tipos_oferta"] or []),
    }


def get_date_bounds() -> tuple[date, date]:
    query = text(f"""
        SELECT
            MIN(fecha_review)::date AS fecha_minima,
            MAX(fecha_review)::date AS fecha_maxima
        FROM {TABLE_NAME}
    """)

    with get_reviews_engine().connect() as connection:
        row = connection.execute(query).mappings().one()

    if not row["fecha_minima"] or not row["fecha_maxima"]:
        raise RuntimeError(
            "No se encontraron fechas válidas en rd_tabla_reviews."
        )

    return row["fecha_minima"], row["fecha_maxima"]


def get_dashboard_metrics(filters: ReviewFilters) -> dict[str, Any]:
    where_sql, params = build_where_clause(filters)

    query = text(f"""
        SELECT
            COUNT(*) AS total_reviews,
            COUNT(DISTINCT ml_id) AS publicaciones_unicas,
            COUNT(DISTINCT sku) AS skus_unicos,
            ROUND(AVG(estrellas)::numeric, 2) AS promedio_estrellas,
            COUNT(*) FILTER (
                WHERE estrellas IN (1, 2)
            ) AS quejas_criticas,
            ROUND(
                100.0 * COUNT(*) FILTER (
                    WHERE estrellas IN (1, 2)
                ) / NULLIF(COUNT(*), 0),
                2
            ) AS porcentaje_quejas_criticas,
            COUNT(*) FILTER (
                WHERE estrellas IN (4, 5)
            ) AS positivas,
            ROUND(
                100.0 * COUNT(*) FILTER (
                    WHERE estrellas IN (4, 5)
                ) / NULLIF(COUNT(*), 0),
                2
            ) AS porcentaje_satisfaccion
        FROM {TABLE_NAME}
        WHERE {where_sql}
    """)

    with get_reviews_engine().connect() as connection:
        row = connection.execute(query, params).mappings().one()

    return dict(row)


def get_rating_distribution(filters: ReviewFilters) -> pd.DataFrame:
    where_sql, params = build_where_clause(filters)

    query = text(f"""
        SELECT
            estrellas,
            COUNT(*) AS reviews
        FROM {TABLE_NAME}
        WHERE {where_sql}
        GROUP BY estrellas
        ORDER BY estrellas DESC
    """)

    with get_reviews_engine().connect() as connection:
        return pd.read_sql(query, connection, params=params)


def get_monthly_trend(filters: ReviewFilters) -> pd.DataFrame:
    where_sql, params = build_where_clause(filters)

    query = text(f"""
        SELECT
            DATE_TRUNC('month', fecha_review)::date AS mes,
            COUNT(*) AS reviews,
            ROUND(AVG(estrellas)::numeric, 2) AS promedio_estrellas,
            COUNT(*) FILTER (
                WHERE estrellas IN (1, 2)
            ) AS quejas_criticas
        FROM {TABLE_NAME}
        WHERE {where_sql}
        GROUP BY 1
        ORDER BY 1
    """)

    with get_reviews_engine().connect() as connection:
        return pd.read_sql(query, connection, params=params)


def get_offer_type_metrics(filters: ReviewFilters) -> pd.DataFrame:
    where_sql, params = build_where_clause(filters)

    query = text(f"""
        SELECT
            COALESCE(
                NULLIF(BTRIM(tipo_oferta), ''),
                'Sin clasificación'
            ) AS tipo_oferta,
            COUNT(*) AS reviews,
            ROUND(AVG(estrellas)::numeric, 2) AS promedio_estrellas,
            ROUND(
                100.0 * COUNT(*) FILTER (
                    WHERE estrellas IN (1, 2)
                ) / NULLIF(COUNT(*), 0),
                2
            ) AS porcentaje_quejas
        FROM {TABLE_NAME}
        WHERE {where_sql}
        GROUP BY 1
        ORDER BY reviews DESC
    """)

    with get_reviews_engine().connect() as connection:
        return pd.read_sql(query, connection, params=params)


def get_alerts(
    filters: ReviewFilters,
    limit: int = 10,
    min_reviews: int = 5,
) -> pd.DataFrame:
    """
    Publicaciones con más reviews críticas.
    `min_reviews` evita destacar un ML_ID con una sola reseña.
    """
    where_sql, params = build_where_clause(filters)

    params.update(
        {
            "limit": limit,
            "min_reviews": min_reviews,
        }
    )

    query = text(f"""
        SELECT
            ml_id,
            MAX(cuenta) AS cuenta,
            MAX(titulo_ecom) AS titulo_ecom,
            MAX(sku) AS sku,
            MAX(tipo_oferta) AS tipo_oferta,
            COUNT(*) AS total_reviews,
            COUNT(*) FILTER (
                WHERE estrellas IN (1, 2)
            ) AS quejas_criticas,
            ROUND(
                100.0 * COUNT(*) FILTER (
                    WHERE estrellas IN (1, 2)
                ) / NULLIF(COUNT(*), 0),
                2
            ) AS porcentaje_quejas,
            ROUND(AVG(estrellas)::numeric, 2) AS promedio_estrellas
        FROM {TABLE_NAME}
        WHERE {where_sql}
        GROUP BY ml_id
        HAVING COUNT(*) >= :min_reviews
        ORDER BY
            quejas_criticas DESC,
            porcentaje_quejas DESC,
            total_reviews DESC,
            ml_id
        LIMIT :limit
    """)

    with get_reviews_engine().connect() as connection:
        return pd.read_sql(query, connection, params=params)


def get_top_rated(
    filters: ReviewFilters,
    limit: int = 10,
    min_reviews: int = 5,
) -> pd.DataFrame:
    where_sql, params = build_where_clause(filters)

    params.update(
        {
            "limit": limit,
            "min_reviews": min_reviews,
        }
    )

    query = text(f"""
        SELECT
            ml_id,
            MAX(cuenta) AS cuenta,
            MAX(titulo_ecom) AS titulo_ecom,
            MAX(sku) AS sku,
            MAX(tipo_oferta) AS tipo_oferta,
            COUNT(*) AS total_reviews,
            ROUND(AVG(estrellas)::numeric, 2) AS promedio_estrellas,
            COUNT(*) FILTER (
                WHERE estrellas IN (4, 5)
            ) AS positivas
        FROM {TABLE_NAME}
        WHERE {where_sql}
        GROUP BY ml_id
        HAVING COUNT(*) >= :min_reviews
        ORDER BY
            promedio_estrellas DESC,
            total_reviews DESC,
            ml_id
        LIMIT :limit
    """)

    with get_reviews_engine().connect() as connection:
        return pd.read_sql(query, connection, params=params)


def get_reviews_page(
    filters: ReviewFilters,
    page: int,
    page_size: int,
) -> tuple[pd.DataFrame, int]:
    """
    Devuelve solo la página solicitada y el conteo total filtrado.
    No descarga toda la tabla.
    """
    where_sql, params = build_where_clause(filters)

    safe_page = max(page, 1)
    safe_page_size = min(max(page_size, 25), 100)

    params.update(
        {
            "limit": safe_page_size,
            "offset": (safe_page - 1) * safe_page_size,
        }
    )

    count_query = text(f"""
        SELECT COUNT(*) AS total
        FROM {TABLE_NAME}
        WHERE {where_sql}
    """)

    page_query = text(f"""
        SELECT
            ml_id,
            cuenta,
            fecha_review,
            estrellas,
            estado_meli,
            titulo_ecom,
            sku,
            tipo_publicacion,
            titulo_meli,
            tipo_oferta,
            titulo_review,
            comentario
        FROM {TABLE_NAME}
        WHERE {where_sql}
        ORDER BY fecha_review DESC, ml_id ASC
        LIMIT :limit
        OFFSET :offset
    """)

    with get_reviews_engine().connect() as connection:
        total = connection.execute(
            count_query,
            params,
        ).scalar_one()

        reviews = pd.read_sql(
            page_query,
            connection,
            params=params,
        )

    return reviews, int(total)
