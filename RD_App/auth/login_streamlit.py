import streamlit as st
from passlib.context import CryptContext

from services.db import fetch_one, execute

pwd_context = CryptContext(
    schemes=["bcrypt"],
    default="bcrypt",
    bcrypt__rounds=12,
    truncate_error=True,
)


def login_local(username, password):
    user = fetch_one(
        "SELECT * FROM rd_usuarios WHERE username = %s AND is_active = true",
        (username,)
    )
    if not user:
        return None

    if not pwd_context.verify(password, user["password_hash"]):
        return None

    return user


def _build_ecom_session(user: dict):
    return {
        "username": user.get("username"),
        "user_id": user.get("id"),
        "authenticated": True,
    }


def login_ecom():
    col1, col2, col3 = st.columns([1, 1.2, 1])

    with col2:
        st.markdown("## RD App")
        st.markdown("Acceso con credenciales EcomExperts")
        st.markdown("---")

        username = st.text_input("Usuario", key="login_username")
        password = st.text_input("Contraseña", type="password", key="login_password")

        if st.button("Ingresar", use_container_width=True, key="btn_login"):
            user = login_local(username, password)

            if user:
                st.session_state["authenticated"] = True
                st.session_state["user_info"] = {
                    "id": user.get("id"),
                    "username": user.get("username"),
                    "name": user.get("nombre") or user.get("username"),
                    "email": user.get("email"),
                }
                st.session_state["ecom_session"] = _build_ecom_session(user)
                st.success("Login exitoso.")
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")

        st.markdown("---")
        with st.expander("Cambiar contraseña"):
            oldpwd = st.text_input("Contraseña actual", type="password", key="oldpwd")
            newpwd = st.text_input("Nueva contraseña", type="password", key="newpwd")
            conpwd = st.text_input("Confirmar nueva contraseña", type="password", key="conpwd")

            if st.button("Actualizar contraseña", key="btn_actualizar_pwd", use_container_width=True):
                if not username.strip():
                    st.error("Ingresa primero tu usuario.")
                elif newpwd != conpwd:
                    st.error("Las contraseñas nuevas no coinciden.")
                elif len(newpwd) < 6:
                    st.error("La nueva contraseña debe tener al menos 6 caracteres.")
                else:
                    user = login_local(username, oldpwd)
                    if not user:
                        st.error("Contraseña actual incorrecta.")
                    else:
                        new_hash = pwd_context.hash(newpwd)
                        execute(
                            "UPDATE rd_usuarios SET password_hash = %s WHERE username = %s",
                            (new_hash, username)
                        )
                        st.success("Contraseña actualizada correctamente.")
