import json
import requests
import streamlit as st
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

LOGIN_URL = "https://api.ecomexperts.com/users/users/doLogin.json"
COMMON_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate",
}
TIMEOUT = (20, 90)


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["POST"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(COMMON_HEADERS)
    return session


def login_session(email: str, password: str) -> requests.Session:
    session = build_session()
    payload_login = {"User": {"email_address": email, "password": password}}

    resp = session.post(LOGIN_URL, data=json.dumps(payload_login), timeout=TIMEOUT)
    resp.raise_for_status()

    try:
        body = resp.json()
    except Exception:
        body = {}

    if isinstance(body, dict) and (body.get("error") or body.get("errors")):
        raise ValueError(body.get("error") or body.get("errors"))

    if len(session.cookies) == 0:
        raise ValueError("No se recibió cookie de sesión válida desde EcomExperts.")

    return session


def login_ecom():
    left, center, right = st.columns([1, 1.15, 1])

    with center:
        st.markdown("## Iniciar sesión")
        st.caption("Acceso con credenciales de EcomExperts")
        st.markdown("---")

        email = st.text_input("Correo EcomExperts", key="ecom_email_input")
        password = st.text_input(
            "Contraseña EcomExperts",
            type="password",
            key="ecom_password_input"
        )

        login_clicked = st.button(
            "Ingresar",
            use_container_width=True,
            type="primary",
            key="btn_login_ecom"
        )

        if login_clicked:
            if not email or not password:
                st.warning("Debes ingresar correo y contraseña de EcomExperts.")
            else:
                try:
                    with st.spinner("Validando credenciales con EcomExperts..."):
                        session = login_session(email, password)

                    st.session_state["authenticated"] = True
                    st.session_state["ecom_session"] = session
                    st.session_state["ecom_email"] = email
                    st.rerun()

                except Exception as e:
                    st.session_state["authenticated"] = False
                    st.session_state["ecom_session"] = None
                    st.session_state["ecom_email"] = None
                    st.error(f"No fue posible validar las credenciales: {e}")
