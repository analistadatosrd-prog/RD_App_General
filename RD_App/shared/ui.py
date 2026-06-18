import streamlit as st
import pandas as pd


def require_auth():
    if not st.session_state.get("authenticated", False):
        st.warning("Debes iniciar sesión para acceder a este módulo.")
        st.stop()


def module_header(title: str, description: str = ""):
    st.title(title)
    if description:
        st.caption(description)
    st.markdown("---")


def dataframe_download_csv(df: pd.DataFrame, filename: str, label: str = "Descargar CSV"):
    if df is None or df.empty:
        st.info("No hay datos para descargar.")
        return

    csv_data = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label=label,
        data=csv_data,
        file_name=filename,
        mime="text/csv",
        use_container_width=True,
    )


def show_user_context():
    user_info = st.session_state.get("user_info")
    if not user_info:
        return

    nombre = user_info.get("name") or user_info.get("username") or "Usuario"
    st.caption(f"Usuario activo: {nombre}")
