import os
import secrets

from fastapi import FastAPI, Header, HTTPException
from google import genai
from pydantic import BaseModel, Field

app = FastAPI(title="RD Vertex Reviews API")

PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
BACKEND_TOKEN = os.environ["BACKEND_TOKEN"]
MODEL_ID = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION,
)


class ReviewChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)
    reviews_context: str = Field(min_length=1, max_length=80_000)


def verify_token(authorization: str | None) -> None:
    expected = f"Bearer {BACKEND_TOKEN}"

    if not authorization or not secrets.compare_digest(
        authorization,
        expected,
    ):
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(
    payload: ReviewChatRequest,
    authorization: str | None = Header(default=None),
):
    verify_token(authorization)

    prompt = f"""
Eres un analista de experiencia de cliente para RD Group.

Responde únicamente con las reseñas que se proporcionan. No inventes
hechos, números, fechas, causas ni conclusiones no sustentadas. Si no
hay evidencia suficiente, indícalo claramente.

Pregunta:
{payload.question}

Reseñas:
{payload.reviews_context}

Responde con:
1. Una respuesta directa.
2. Hallazgos principales en viñetas.
3. Evidencia, citando los IDs o fechas disponibles.
4. Una recomendación práctica, solo si está respaldada por las reseñas.
""".strip()

    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
        )

        return {
            "answer": response.text or "No fue posible generar una respuesta."
        }

    except Exception:
        raise HTTPException(
            status_code=502,
            detail="No fue posible consultar Vertex AI.",
        )
