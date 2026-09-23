import pandas as pd
import requests
import streamlit as st
from sqlalchemy import create_engine, text


MAX_REVIEWS = 30
MAX_CHARS_PER_REVIEW = 1_500
REQUEST_TIMEOUT_SECONDS = 90


@st.cache_resource
def get_engine():
    database_url = st.secrets.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "Falta DATABASE_URL en los Secrets de Streamlit."
        )

    return create_engine(
        database_url,
        pool_pre_ping=True,
    )


def clean_text(value) -> str:
    if value is None:
        return ""

    return " ".join(str(value).split())


def get_reviews(limit: int = MAX_REVIEWS) -> pd.DataFrame:
    """
    Recupera las reviews más recientes desde PostgreSQL.

    Ajusta los nombres de columnas si tu tabla rd_tabla_reviews usa otros
    nombres. La consulta no recibe texto libre del usuario, por lo que no
    construye SQL dinámico desde la pregunta.
    """
    query = text("""
        SELECT *
        FROM rd_tabla_reviews
        ORDER BY 1 DESC
        LIMIT :limit
    """)

    with get_engine().connect() as connection:
        return pd.read_sql(
            query,
            connection,
            params={"limit": limit},
        )


def find_column(columns, candidates):
    normalized = {
        str(column).lower().strip(): column
        for column in columns
    }

    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]

    return None


def reviews_to_context(reviews: pd.DataFrame) -> str:
    """
    Convierte las filas de PostgreSQL en texto para Vertex AI.
    Detecta nombres de columnas frecuentes para id, fecha, puntuación y texto.
    """
    if reviews.empty:
        return "No se encontraron reseñas para analizar."

    id_column = find_column(
        reviews.columns,
        [
