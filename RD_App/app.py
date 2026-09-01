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
    "persistent_session_token": None,
    "persistent_session_expires_at": None,
}

for key, value in DEFAULT_SESSION_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


def restore_session_if_needed():
    """
    Restaura la sesión de RD App desde ?rd_session=TOKEN.

    Si el token sigue vigente en rd_sesiones_app, se recupera la sesión
    incluso después de F5 o de volver a abrir la URL desde el historial.
    """
    if st.session_state.get("authenticated"):
        return

    try:
        session_data = restore_persistent_session()
    except Exception:
        session_data = None

    if not session_data:
        return

    st.session_state["authenticated"] = True
    st.session_state["ecom_email"] = session_data["email"]
    st.session_state["persistent_session_token"] = (
        session_data["session_token"]
    )
    st.session_state["persistent_session_expires_at"] = (
        session_data["expires_at"]
    )

    # La requests.Session de EcomExperts no puede guardarse de manera
    # segura en URL ni SQL. Esta se debe regenerar si un módulo exige API.
    st.session_state["ecom_session"] = None


def logout():
    token = st.session_state.get(
        "persistent_session_token"
    )

    try:
        revoke_persistent_session(token)
    except Exception:
        pass

    st.session_state["authenticated"] = False
    st.session_state["ecom_session"] = None
    st.session_state["ecom_email"] = None
    st.session_state["persistent_session_token"] = None
    st.session_state["persistent_session_expires_at"] = None

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
