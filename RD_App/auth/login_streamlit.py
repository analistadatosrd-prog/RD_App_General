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

SESSION_DURATION_HOURS = 5

LOCAL_STORAGE_KEY = "rd_app_session_token"
LOCAL_STORAGE_MANAGER_KEY = "rd_app_local_storage_manager"


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

    if isinstance(body, dict):
        if body.get("error") or body.get("errors"):
            raise ValueError(
                body.get("error") or body.get("errors")
            )

        if body.get("success") is False:
            raise ValueError(
                "EcomExperts rechazó las credenciales."
            )

    if len(session.cookies) == 0:
        raise ValueError(
            "No se recibió una cookie de sesión válida desde EcomExperts."
        )

    return session


def get_local_storage_manager():
    """
    Gestor persistente del navegador.

    Usa localStorage, por lo que no depende de query params.
    Esto permite restaurar la sesión después de navegar entre módulos,
    refrescar con F5 o reabrir el navegador.
    """
    return stx.LocalStorage(
        key=LOCAL_STORAGE_MANAGER_KEY
    )


def utc_now():
    return datetime.now(timezone.utc)


def create_session_token():
    return secrets.token_urlsafe(48)


def create_persistent_session(email: str):
    """
    Crea una sesión temporal de cinco horas en SQL y devuelve el token.
    """
    clean_email = str(email or "").strip()

    if not clean_email:
        raise ValueError(
            "No se puede crear una sesión persistente sin correo."
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

    return {
        "session_token": token,
        "email": clean_email,
        "created_at": created_at,
        "expires_at": expires_at,
    }


def save_session_token_in_browser(token: str):
    """
    Guarda el token opaco en localStorage del navegador.
    No se guarda correo ni contraseña.
    """
    storage = get_local_storage_manager()
    storage.setItem(
        LOCAL_STORAGE_KEY,
        str(token),
    )


def get_session_token_from_browser():
    """
    Lee el token guardado en localStorage.

    Retorna:
    - pending: el componente frontend todavía está cargando.
    - missing: no existe token.
    - found: token disponible.
    """
    storage = get_local_storage_manager()

    try:
        token = storage.getItem(LOCAL_STORAGE_KEY)
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


def remove_session_token_from_browser():
    """
    Elimina la referencia local a la sesión cuando el usuario cierra sesión
    o cuando SQL determina que el token venció/revocó.
    """
    try:
        storage = get_local_storage_manager()
        storage.deleteItem(LOCAL_STORAGE_KEY)
    except Exception:
        pass


def validate_persistent_session(token):
    """
    Valida token contra SQL y actualiza last_seen_at.
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


def restore_persistent_session():
    """
    Intenta restaurar el acceso de RD App desde localStorage + SQL.
    """
    browser_state = get_session_token_from_browser()

    if browser_state["status"] == "pending":
        return {
            "status": "pending",
            "session": None,
        }

    if browser_state["status"] == "missing":
        return {
            "status": "missing",
            "session": None,
        }

    token = browser_state["token"]

    session_data = validate_persistent_session(token)

    if not session_data:
        remove_session_token_from_browser()

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


def revoke_persistent_session(token=None):
    """
    Revoca la sesión de SQL y borra token local del navegador.
    """
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

    remove_session_token_from_browser()


def cleanup_old_sessions():
    """
    Limpieza opcional de registros vencidos hace más de 7 días.
    """
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
            clean_email = email.strip()

            with st.spinner(
                "Validando credenciales con EcomExperts..."
            ):
                ecom_session = login_session(
                    email=clean_email,
                    password=password,
                )

            with st.spinner(
                "Creando sesión segura de cinco horas..."
            ):
                persistent_session = create_persistent_session(
                    email=clean_email
                )

                save_session_token_in_browser(
                    persistent_session["session_token"]
                )

            st.session_state["authenticated"] = True
            st.session_state["ecom_session"] = ecom_session
            st.session_state["ecom_email"] = clean_email
            st.session_state["persistent_session_token"] = (
                persistent_session["session_token"]
            )
            st.session_state["persistent_session_expires_at"] = (
                persistent_session["expires_at"]
            )
            st.session_state["persistent_session_checked"] = True
            st.session_state["persistent_restore_attempts"] = 0

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

            st.error(
                f"No fue posible validar las credenciales: {exc}"
            )
