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
    "persistent_restore_status": "Sin verificar",
}

for key, value in DEFAULT_SESSION_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


def restore_session_if_needed():
    """
    Intenta restaurar la sesión persistente desde una cookie del navegador.

    La lectura inicial de cookies con extra_streamlit_components puede tardar
    uno o más reruns. Por eso no se interpreta la ausencia inicial de token
    como logout inmediato.

    Estados posibles:
    - pending: cookie manager todavía cargando.
    - missing: no existe cookie en el navegador.
    - invalid: existe cookie pero token vencido o revocado en SQL.
    - valid: token vigente y restaurado.
    """
    if st.session_state.get("authenticated"):
        return

    if st.session_state.get("persistent_session_checked"):
        return

    try:
        restore_result = restore_persistent_session()
    except Exception as exc:
        st.session_state["persistent_restore_status"] = (
            f"Error al leer sesión persistente: {exc}"
        )
        st.session_state["persistent_session_checked"] = True
        return

    restore_status = restore_result.get("status", "missing")
    restored_session = restore_result.get("session")

    st.session_state["persistent_restore_status"] = restore_status

    if restore_status == "pending":
        attempts = int(
            st.session_state.get(
                "persistent_restore_attempts",
                0,
            )
        )

        if attempts < 8:
            st.session_state["persistent_restore_attempts"] = (
                attempts + 1
            )

            time.sleep(0.35)
            st.rerun()

        st.session_state["persistent_restore_status"] = (
            "No fue posible leer la cookie después de varios intentos."
        )

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

    st.session_state["persistent_restore_status"] = (
        "Sesión restaurada correctamente."
    )

    # La requests.Session de EcomExperts existe solamente en memoria.
    # Se pierde al refrescar o cerrar el navegador y no se debe guardar
    # serializada en SQL/cookies. La sesión de RD App queda restaurada.
    st.session_state["ecom_session"] = None


def logout():
    """
    Cierra completamente la sesión del usuario.

    - Revoca el token SQL.
    - Elimina la cookie del navegador.
    - Limpia session_state.
    """
    token = st.session_state.get(
        "persistent_session_token"
    )

    try:
        revoke_persistent_session(token)
    except Exception as exc:
        st.warning(
            f"No fue posible revocar la sesión persistente: {exc}"
        )

    st.session_state["authenticated"] = False
    st.session_state["ecom_session"] = None
    st.session_state["ecom_email"] = None
    st.session_state["persistent_session_token"] = None
    st.session_state["persistent_session_expires_at"] = None
    st.session_state["persistent_session_checked"] = True
    st.session_state["persistent_restore_attempts"] = 0
    st.session_state["persistent_restore_status"] = (
        "Sesión cerrada manualmente."
    )

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

        email = st.session_state.get("ecom_email")
        if email:
            st.caption(
                f"Sesión iniciada: {email}"
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

        # Diagnóstico temporal.
        # Elimina este bloque cuando confirmemos que la persistencia funciona.
        with st.expander(
            "Diagnóstico de sesión",
            expanded=False,
        ):
            st.write(
                "Estado restauración:",
                st.session_state.get(
                    "persistent_restore_status"
                ),
            )

            st.write(
                "Intentos de cookie:",
                st.session_state.get(
                    "persistent_restore_attempts"
                ),
            )

            token = st.session_state.get(
                "persistent_session_token"
            )

            if token:
                st.code(
                    f"{token[:12]}...{token[-8:]}",
                    language=None,
                )
            else:
                st.caption(
                    "No hay token persistente en session_state."
                )

            try:
                st.write(
                    "Cookies detectadas por Streamlit:",
                    dict(st.context.cookies),
                )
            except Exception:
                st.caption(
                    "No fue posible leer st.context.cookies."
                )

    pg = st.navigation(
        build_navigation(),
        position="sidebar",
        expanded=True,
    )

    pg.run()

else:
    login_ecom()

    # Diagnóstico temporal para el caso de usuario no restaurado.
    with st.expander(
        "Diagnóstico de sesión",
        expanded=False,
    ):
        st.write(
            "Estado restauración:",
            st.session_state.get(
                "persistent_restore_status"
            ),
        )

        st.write(
            "Intentos de cookie:",
            st.session_state.get(
                "persistent_restore_attempts"
            ),
        )

        try:
            st.write(
                "Cookies detectadas por Streamlit:",
                dict(st.context.cookies),
            )
        except Exception:
            st.caption(
                "No fue posible leer st.context.cookies."
            )
