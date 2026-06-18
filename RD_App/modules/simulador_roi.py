import streamlit as st

from shared.ui import require_auth, module_header, show_user_context

require_auth()

module_header(
    "Simulador ROI",
    "Módulo de simulación de rentabilidad/ROI sobre publicaciones."
)
show_user_context()

st.info(
    "Este módulo ya quedó integrado en la arquitectura general. "
    "En el siguiente paso moveremos aquí el simulador ROI completo que ya desarrollamos."
)

st.markdown("### Estado del módulo")
st.write(
    "La estructura multipágina ya reconoce este espacio como el módulo oficial del simulador. "
    "A partir de aquí reemplazaremos este contenido por la lógica real."
)
