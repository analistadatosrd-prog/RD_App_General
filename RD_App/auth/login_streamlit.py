import json
import secrets
from datetime import datetime, timedelta, timezone

import extra_streamlit_components as stx
import requests
import streamlit as st
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from services.db import execute, fetch_all


LOGIN_URL = "https://api.ecomexperts.com/users/users/doLogin.json"

COMMON_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate",
}

TIMEOUT = (20, 90)

COOKIE_NAME = "rd_app_session"
COOKIE_MANAGER_KEY = "rd_app_cookie_manager"

SESSION_DURATION_HOURS = 5


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

    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=20,
        pool_maxsize=20,
    )

    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(COMMON_HEADERS)

    return session


def login_session(email: str, password: str) -> requests.Session:
    session = build_session()

    payload_login = {
        "User": {
            "email_address": email,
            "password": password,
        }
    }

    response = session.post(
        LOGIN_URL,
        data=json.dumps(payload_login),
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    try:
        body = response.json()
    except Exception:
        body = {}

    if isinstance(body, dict) and (
        body.get("error") or body.get("errors")
    ):
        raise ValueError(
            body.get("error") or body.get("errors")
        )

    if len(session.cookies) == 0:
        raise ValueError(
            "No se recibió cookie de sesión válida desde EcomExperts."
        )

    return session


def get_cookie_manager():
    """
    Instancia estable del administrador de cookies.

    Importante: la key no puede cambiar entre renders, porque Streamlit
    debe reconocer el mismo componente después de un refresh.
    """
    return stx.CookieManager(
        key=COOKIE_MANAGER_KEY
    )


def utc_now():
    return datetime.now(timezone.utc)


def create_session_token():
    return secrets.token_urlsafe(48)


def create_persistent_session(email: str):
    """
    Crea la sesión persistente en SQL y guarda el token en el navegador.
    """
    clean_email = str(email or "").strip()

    if not clean_email:
        raise ValueError(
            "No se puede crear la sesión persistente: email vacío."
        )

    token = create_session_token()
    created_at = utc_now()
    expires_at = created_at + timedelta(
        hours=SESSION_DURATION_HOURS
    )

    execute(
        """
        INSERT INTO rd_sesiones_app (
            session_token,
            email,
            created_at,
            expires_at,
            last_seen_at
        )
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            token,
            clean_email,
            created_at,
            expires_at,
            created_at,
        ),
    )

    cookie_manager = get_cookie_manager()

    cookie_manager.set(
        COOKIE_NAME,
        token,
        expires_at=expires_at,
    )

    st.session_state["persistent_session_token"] = token
    st.session_state["persistent_session_expires_at"] = expires_at

    return {
        "session_token": token,
        "expires_at": expires_at,
    }


def get_cookie_state():
    """
    Lee únicamente la cookie rd_app_session.

    Es más estable que get_all() porque evita depender de la respuesta
    completa del componente de cookies.
    """
    cookie_manager = get_cookie_manager()

    try:
        token = cookie_manager.get(COOKIE_NAME)
    except Exception:
        return {
            "status": "pending",
            "token": None,
        }

    if token is None:
        return {
            "status": "pending",
            "token": None,
        }

    token = str(token).strip()

    if not token:
        return {
            "status": "missing",
            "token": None,
        }

    return {
        "status": "found",
        "token": token,
    }


def validate_persistent_session(token):
    """
    Comprueba que exista una sesión activa, no revocada y no vencida.
    """
    if not token:
        return None

    rows = fetch_all(
        """
        SELECT
            id,
            session_token,
            email,
            created_at,
            expires_at,
            revoked_at,
            last_seen_at
        FROM rd_sesiones_app
        WHERE session_token = %s
          AND revoked_at IS NULL
          AND expires_at > NOW()
        LIMIT 1
        """,
        (str(token),),
    )

    if not rows:
        return None

    session_data = dict(rows[0])

    execute(
        """
        UPDATE rd_sesiones_app
        SET last_seen_at = NOW()
        WHERE session_token = %s
          AND revoked_at IS NULL
          AND expires_at > NOW()
        """,
        (str(token),),
    )

    return session_data


def clear_persistent_cookie():
    try:
        cookie_manager = get_cookie_manager()
        cookie_manager.delete(COOKIE_NAME)
    except Exception:
        pass


def revoke_persistent_session(token=None):
    if token:
        execute(
            """
            UPDATE rd_sesiones_app
            SET revoked_at = NOW()
            WHERE session_token = %s
              AND revoked_at IS NULL
            """,
            (str(token),),
        )

    clear_persistent_cookie()


def restore_persistent_session():
    """
    Recupera la sesión persistente desde la cookie y SQL.
    """
    cookie_state = get_cookie_state()

    if cookie_state["status"] == "pending":
        return {
            "status": "pending",
            "session": None,
        }

    if cookie_state["status"] == "missing":
        return {
            "status": "missing",
            "session": None,
        }

    token = cookie_state["token"]
    session_data = validate_persistent_session(token)

    if not session_data:
        clear_persistent_cookie()

        return {
            "status": "invalid",
            "session": None,
        }

    st.session_state["persistent_session_token"] = token
    st.session_state["persistent_session_expires_at"] = (
        session_data["expires_at"]
    )

    return {
        "status": "valid",
        "session": session_data,
    }


def cleanup_old_sessions():
    execute(
        """
        DELETE FROM rd_sesiones_app
        WHERE expires_at < NOW() - INTERVAL '7 days'
        """
    )


def login_ecom():
    left, center, right = st.columns([1, 1.15, 1])

    with center:
        st.markdown("## Iniciar sesión")
        st.caption("Acceso con credenciales de EcomExperts")
        st.markdown("---")

        email = st.text_input(
            "Correo EcomExperts",
            key="ecom_email_input",
        )

        password = st.text_input(
            "Contraseña EcomExperts",
            type="password",
            key="ecom_password_input",
        )

        login_clicked = st.button(
            "Ingresar",
            use_container_width=True,
            type="primary",
            key="btn_login_ecom",
        )

        if not login_clicked:
            return

        if not email or not password:
            st.warning(
                "Debes ingresar correo y contraseña de EcomExperts."
            )
            return

        try:
            with st.spinner(
                "Validando credenciales con EcomExperts..."
            ):
                session = login_session(
                    email=email.strip(),
                    password=password,
                )

            with st.spinner(
                "Creando sesión persistente de cinco horas..."
            ):
                persistent_session = create_persistent_session(
                    email=email.strip()
                )

            st.session_state["authenticated"] = True
            st.session_state["ecom_session"] = session
            st.session_state["ecom_email"] = email.strip()
            st.session_state["persistent_session_token"] = (
                persistent_session["session_token"]
            )
            st.session_state["persistent_session_expires_at"] = (
                persistent_session["expires_at"]
            )
            st.session_state["persistent_session_checked"] = True

            try:
                cleanup_old_sessions()
            except Exception:
                pass

            st.rerun()

        except Exception as exc:
            st.session_state["authenticated"] = False
            st.session_state["ecom_session"] = None
            st.session_state["ecom_email"] = None
            st.session_state["persistent_session_token"] = None
            st.session_state["persistent_session_expires_at"] = None
            st.session_state["persistent_session_checked"] = True

            st.error(
                f"No fue posible validar las credenciales: {exc}"
            )
