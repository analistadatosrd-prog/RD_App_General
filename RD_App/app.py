import time

import streamlit as st

from auth.login_streamlit import (
    login_ecom,
    restore_persistent_session,
    revoke_persistent_session,
)

st.set_page_config(
    page_title="RD App",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_SESSION_STATE = {
    "authenticated": False,
    "ecom_session": None,
    "ecom_email": None,
    "persistent_session_checked": False,
    "persistent_session_token": None,
    "persistent_session_expires_at": None,
    "persistent_restore_attempts": 0,
}

for key, value in DEFAULT_SESSION_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


def restore_session_if_needed():
    """
    Intenta recuperar la sesión persistente del navegador.

    La lectura de cookies puede requerir uno o más renders de Streamlit.
    Por eso, si el estado es pending, se hace rerun antes de concluir
    que no hay una sesión válida.
    """
    if st.session_state.get("authenticated"):
        return

    if st.session_state.get("persistent_session_checked"):
        return

    restore_result = restore_persistent_session()
    restore_status = restore_result.get("status")
    restored_session = restore_result.get("session")

    if restore_status == "pending":
        attempts = int(
            st.session_state.get(
                "persistent_restore_attempts",
                0,
            )
        )

        if attempts < 3:
            st.session_state["persistent_restore_attempts"] = (
                attempts + 1
            )

            time.sleep(0.2)
            st.rerun()

        # Después de algunos intentos, no bloqueamos el acceso.
        # El usuario podrá iniciar sesión manualmente si el navegador
        # bloqueó cookies o la dependencia no está instalada.
        st.session_state["persistent_session_checked"] = True
        return

    st.session_state["persistent_session_checked"] = True

    if restore_status != "valid" or not restored_session:
        return

    st.session_state["authenticated"] = True
    st.session_state["ecom_email"] = restored_session["email"]
    st.session_state["persistent_session_token"] = (
        restored_session["session_token"]
    )
    st.session_state["persistent_session_expires_at"] = (
        restored_session["expires_at"]
    )

    # La requests.Session de EcomExperts no se puede persistir de forma
    # segura dentro de una cookie o una tabla SQL. Se crea durante login
    # y existe mientras la sesión Streamlit actual está activa.
    #
    # RD App permanece autenticada con el token SQL por 5 horas.
    st.session_state["ecom_session"] = None


def logout():
    token = st.session_state.get("persistent_session_token")

    try:
        revoke_persistent_session(token)
    except Exception:
        pass

    st.session_state["authenticated"] = False
    st.session_state["ecom_session"] = None
    st.session_state["ecom_email"] = None
    st.session_state["persistent_session_token"] = None
    st.session_state["persistent_session_expires_at"] = None
    st.session_state["persistent_session_checked"] = True
    st.session_state["persistent_restore_attempts"] = 0

    st.rerun()


def build_navigation():
    return [
        st.Page(
            "modules/informe_inventarios.py",
            title="Informe de inventarios",
            icon="📦",
            default=True,
        ),
        st.Page(
            "modules/informe_costos_foxy.py",
            title="Informe de costos Foxy",
            icon="💰",
        ),
        st.Page(
            "modules/informe_roi.py",
            title="Informe ROI",
            icon="📈",
        ),
        st.Page(
            "modules/simulador_roi.py",
            title="Simulador ROI",
            icon="🧮",
        ),
        st.Page(
            "modules/reporte_cambios.py",
            title="Reporte de Cambios",
            icon="📝",
        ),
        st.Page(
            "modules/reporte_envios.py",
            title="Reporte de Envíos",
            icon="🚚",
        ),
    ]


restore_session_if_needed()

if st.session_state.get("authenticated"):
    with st.sidebar:
        st.markdown("## RD App")

        if st.session_state.get("ecom_email"):
            st.caption(
                f"Sesión iniciada: {st.session_state['ecom_email']}"
            )

        expires_at = st.session_state.get(
            "persistent_session_expires_at"
        )

        if expires_at:
            st.caption(
                f"Sesión válida hasta: {expires_at}"
            )

        st.markdown("---")

        if st.button(
            "Cerrar sesión",
            use_container_width=True,
        ):
            logout()

    pg = st.navigation(
        build_navigation(),
        position="sidebar",
        expanded=True,
    )

    pg.run()

else:
    login_ecom()
