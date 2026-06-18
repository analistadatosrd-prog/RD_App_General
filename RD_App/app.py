import streamlit as st

from auth.login_streamlit import login_ecom

st.set_page_config(
    page_title="RD App",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ───────────────────────── SESSION STATE BASE ──────────────────────────
DEFAULT_SESSION_STATE = {
    "authenticated": False,
    "ecom_session": None,
    "user_info": None,
}

for key, value in DEFAULT_SESSION_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


def logout():
    st.session_state["authenticated"] = False
    st.session_state["ecom_session"] = None
    st.session_state["user_info"] = None
    st.rerun()


def login_page():
    st.title("RD App")
    st.caption("Acceso centralizado con credenciales EcomExperts.")
    login_ecom()


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
    ]


if st.session_state.get("authenticated"):
    with st.sidebar:
        st.markdown("## RD App")
        user_info = st.session_state.get("user_info")
        if user_info:
            nombre = user_info.get("name") or user_info.get("username") or "Usuario"
            st.caption(f"Sesión iniciada: {nombre}")

        st.markdown("---")
        if st.button("Cerrar sesión", use_container_width=True):
            logout()

    pg = st.navigation(
        build_navigation(),
        position="sidebar",
        expanded=True,
    )
else:
    pg = st.navigation(
        [
            st.Page(login_page, title="Login", icon="🔐", default=True),
        ],
        position="hidden",
    )

pg.run()
