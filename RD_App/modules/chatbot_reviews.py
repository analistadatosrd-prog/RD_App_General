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
            "id",
            "review_id",
            "id_review",
            "id_reseña",
            "id_resena",
        ],
    )

    date_column = find_column(
        reviews.columns,
        [
            "fecha",
            "date",
            "created_at",
            "created",
            "review_date",
            "fecha_review",
        ],
    )

    rating_column = find_column(
        reviews.columns,
        [
            "rating",
            "calificacion",
            "calificación",
            "estrellas",
            "score",
            "puntuacion",
            "puntuación",
        ],
    )

    text_column = find_column(
        reviews.columns,
        [
            "review",
            "review_text",
            "comentario",
            "comentarios",
            "texto",
            "descripcion",
            "descripción",
            "content",
            "mensaje",
        ],
    )

    if not text_column:
        raise ValueError(
            "No se encontró una columna de texto de reseña. "
            "Revisa los nombres de columnas de rd_tabla_reviews "
            "y ajusta la lista de candidatos en reviews_to_context()."
        )

    context_items = []

    for row_number, (_, row) in enumerate(reviews.iterrows(), start=1):
        review_id = (
            clean_text(row[id_column])
            if id_column else f"fila-{row_number}"
        )

        review_date = (
            clean_text(row[date_column])
            if date_column else "sin fecha"
        )

        rating = (
            clean_text(row[rating_column])
            if rating_column else "sin calificación"
        )

        review_text = clean_text(row[text_column])

        if not review_text:
            continue

        review_text = review_text[:MAX_CHARS_PER_REVIEW]

        context_items.append(
            f"[Review {review_id} | Fecha: {review_date} | "
            f"Calificación: {rating}]\n"
            f"{review_text}"
        )

    if not context_items:
        return "No se encontraron textos de reseñas para analizar."

    return "\n\n".join(context_items)


def ask_vertex_reviews(question: str, reviews_context: str) -> str:
    api_url = st.secrets.get("VERTEX_REVIEWS_API_URL")
    api_token = st.secrets.get("VERTEX_REVIEWS_API_TOKEN")

    if not api_url:
        raise RuntimeError(
            "Falta VERTEX_REVIEWS_API_URL en los Secrets de Streamlit."
        )

    if not api_token:
        raise RuntimeError(
            "Falta VERTEX_REVIEWS_API_TOKEN en los Secrets de Streamlit."
        )

    response = requests.post(
        api_url.rstrip("/") + "/chat",
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        json={
            "question": question,
            "reviews_context": reviews_context,
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    if response.status_code == 401:
        raise RuntimeError(
            "Cloud Run rechazó el token. Verifica que "
            "VERTEX_REVIEWS_API_TOKEN en Streamlit sea exactamente igual "
            "a BACKEND_TOKEN configurado en Cloud Run."
        )

    if response.status_code == 502:
        raise RuntimeError(
            "El backend de Cloud Run no pudo consultar Vertex AI. "
            "Revisa los logs de rd-vertex-reviews-api en Google Cloud."
        )

    response.raise_for_status()

    data = response.json()
    answer = data.get("answer")

    if not answer:
        raise RuntimeError(
            "El backend no devolvió el campo 'answer'."
        )

    return answer


def render_reviews_preview(reviews: pd.DataFrame) -> None:
    with st.expander(
        f"Ver las {len(reviews)} reseñas enviadas para análisis"
    ):
        st.dataframe(
            reviews,
            use_container_width=True,
            hide_index=True,
        )


def run():
    st.title("💬 Chatbot de Reviews")
    st.caption(
        "Consulta y análisis de reseñas mediante Vertex AI."
    )

    st.info(
        f"El análisis utiliza hasta {MAX_REVIEWS} reseñas recientes. "
        "No se debe incluir información personal sensible en los textos "
        "enviados al modelo."
    )

    if "reviews_chat_history" not in st.session_state:
        st.session_state.reviews_chat_history = []

    try:
        reviews = get_reviews()
        reviews_context = reviews_to_context(reviews)

    except Exception as exc:
        st.error(
            "No fue posible obtener las reseñas desde PostgreSQL."
        )
        st.exception(exc)
        return

    render_reviews_preview(reviews)

    for message in st.session_state.reviews_chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    question = st.chat_input(
        "Ejemplo: ¿Cuáles son los principales problemas reportados?"
    )

    if not question:
        return

    st.session_state.reviews_chat_history.append(
        {
            "role": "user",
            "content": question,
        }
    )

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Analizando reseñas con Vertex AI..."):
            try:
                answer = ask_vertex_reviews(
                    question=question,
                    reviews_context=reviews_context,
                )

                st.markdown(answer)

            except requests.Timeout:
                answer = (
                    "La consulta tardó demasiado. Intenta nuevamente con "
                    "una pregunta más específica."
                )
                st.error(answer)

            except requests.RequestException as exc:
                answer = (
                    "No fue posible conectar con el servicio de análisis."
                )
                st.error(answer)
                st.caption(str(exc))

            except Exception as exc:
                answer = (
                    "Ocurrió un error al analizar las reseñas."
                )
                st.error(answer)
                st.caption(str(exc))

    st.session_state.reviews_chat_history.append(
        {
            "role": "assistant",
            "content": answer,
        }
    )


if __name__ == "__main__":
    run()
