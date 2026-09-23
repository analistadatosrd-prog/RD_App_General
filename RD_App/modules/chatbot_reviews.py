import streamlit as st
from google import genai

st.title("Prueba de Gemini")

try:
    client = genai.Client(
        api_key=st.secrets["GEMINI_API_KEY"]
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Responde exactamente: conexión correcta.",
    )

    st.success(response.text)

except KeyError:
    st.error("Falta GEMINI_API_KEY en Streamlit Secrets.")

except Exception as exc:
    st.error(f"Error al conectar con Gemini: {exc}")
