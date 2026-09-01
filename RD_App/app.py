import streamlit as st

from auth.login_streamlit import (
    login_ecom,
    restore_persistent_session,
    revoke_persistent_session,
    set_url_session_token,
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
    Recupera la sesión persistente desde el token incluido en la URL.

    Si el token existe y permanece vigente en rd_sesiones_app,
    se restaura automáticamente el acceso de RD App.
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

    # La sesión de EcomExperts existe en memoria durante la sesión actual.
    # La sesión de RD App se restaura con la vigencia definida en SQL.
    st.session_state["ecom_session"] = None


def preserve_session_token_in_url():
    """
    Streamlit puede limpiar los query params al cambiar entre módulos.
    Esta función vuelve a establecer el token mientras la sesión
    permanezca autenticada.
    """
    if not st.session_state.get("authenticated"):
        return

    token = st.session_state.get(
        "persistent_session_token"
    )

    if token:
        set_url_session_token(token)


def logout():
    """
    Cierra sesión completamente:

    - Revoca el token en SQL.
    - Elimina el token de la URL.
    - Limpia la sesión activa de Streamlit.
    """
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
preserve_session_token_in_url()

if st.session_state.get("authenticated"):
    with st.sidebar:
        st.markdown("## RD App")

        if st.session_state.get("ecom_email"):
            st.caption(
                f"Sesión iniciada: {st.session_state['ecom_email']}"
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
