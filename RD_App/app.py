import streamlit as st

from auth.login_streamlit import login_ecom
from auth.login_streamlit import restore_persistent_session
from auth.login_streamlit import revoke_persistent_session

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
}

for key, value in DEFAULT_SESSION_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


def restore_session_if_needed():
    """
    Valida una sola vez la cookie persistente del navegador.

    Si el usuario vuelve a entrar dentro de la ventana de cinco horas,
    restaura la autenticación de RD App sin pedirle usuario y contraseña.
    """
    if st.session_state.get("persistent_session_checked"):
        return

    st.session_state["persistent_session_checked"] = True

    if st.session_state.get("authenticated"):
        return

    try:
        persistent_session = restore_persistent_session()
    except Exception:
        persistent_session = None

    if not persistent_session:
        return

    st.session_state["authenticated"] = True
    st.session_state["ecom_email"] = persistent_session["email"]

    # La sesión requests.Session de EcomExperts no se puede guardar
    # directamente en SQL ni serializar de forma segura.
    #
    # Por eso, al volver a abrir la página se restaura la sesión interna
    # de RD App, pero ecom_session debe regenerarse si algún módulo
    # requiere conectarse a EcomExperts.
    #
    # Por ahora queda vacía hasta agregar restauración específica:
    st.session_state["ecom_session"] = None


def logout():
    """
    Cierra de manera completa:
    - revoca el token persistente en SQL;
    - elimina la cookie del navegador;
    - limpia la sesión actual de Streamlit.
    """
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
