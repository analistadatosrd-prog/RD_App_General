from datetime import datetime, timedelta, timezone
import secrets

import extra_streamlit_components as stx
import streamlit as st

from services.db import execute, fetch_all


COOKIE_NAME = "rd_app_session"
SESSION_DURATION_HOURS = 5


def get_cookie_manager():
    """
    Devuelve una instancia del gestor de cookies.
    Debe utilizarse una clave estable para que funcione
    correctamente entre reruns y páginas de Streamlit.
    """
    return stx.CookieManager(key="rd_app_cookie_manager")


def now_utc():
    return datetime.now(timezone.utc)


def create_session_token():
    """
    Token criptográficamente seguro y opaco.
    No contiene email, contraseña, roles ni datos sensibles.
    """
    return secrets.token_urlsafe(48)


def create_persistent_session(email):
    """
    Crea una sesión de cinco horas en SQL y guarda el identificador
    aleatorio de esa sesión dentro de una cookie del navegador.
    """
    if not email:
        raise ValueError("No fue posible crear sesión persistente: email vacío.")

    token = create_session_token()
    expires_at = now_utc() + timedelta(hours=SESSION_DURATION_HOURS)

    execute(
        """
        INSERT INTO rd_sesiones_app (
            session_token,
            email,
            expires_at,
            last_seen_at
        )
        VALUES (%s, %s, %s, %s)
        """,
        (
            token,
            str(email).strip(),
            expires_at,
            now_utc(),
        ),
    )

    cookie_manager = get_cookie_manager()

    cookie_manager.set(
        COOKIE_NAME,
        token,
        expires_at=expires_at,
    )

    return {
        "session_token": token,
        "expires_at": expires_at,
    }


def get_cookie_token():
    """
    Lee el token de sesión persistente desde el navegador.
    """
    cookie_manager = get_cookie_manager()
    return cookie_manager.get(COOKIE_NAME)


def get_valid_persistent_session(token):
    """
    Valida que:
    - El token exista.
    - La sesión no haya sido revocada.
    - La sesión no haya superado cinco horas.

    Retorna el email asociado o None si no es válida.
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
        """,
        (str(token),),
    )

    return session_data


def revoke_persistent_session(token=None):
    """
    Revoca una sesión en la base de datos y borra la cookie local.
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

    cookie_manager = get_cookie_manager()
    cookie_manager.delete(COOKIE_NAME)


def cleanup_expired_sessions():
    """
    Limpieza opcional de sesiones vencidas.
    No es obligatorio ejecutarla en cada carga, pero se puede llamar
    al iniciar sesión o una vez al día desde un job externo.
    """
    execute(
        """
        DELETE FROM rd_sesiones_app
        WHERE expires_at < NOW() - INTERVAL '7 days'
        """
    )


def restore_persistent_session():
    """
    Busca el token en la cookie y lo valida contra la tabla SQL.

    No regenera automáticamente ecom_session porque la función de login
    depende de tu archivo auth/login_streamlit.py. Esta función retorna
    el email validado para que app.py o login_streamlit.py reconstruyan
    esa sesión.
    """
    token = get_cookie_token()

    if not token:
        return None

    session_data = get_valid_persistent_session(token)

    if not session_data:
        cookie_manager = get_cookie_manager()
        cookie_manager.delete(COOKIE_NAME)
        return None

    st.session_state["persistent_session_token"] = token
    st.session_state["persistent_session_expires_at"] = session_data["expires_at"]

    return session_data
