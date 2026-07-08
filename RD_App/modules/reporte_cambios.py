import streamlit as st

st.set_page_config(
    page_title="Reporte de Cambios",
    page_icon="📝",
    layout="wide",
)

st.title("Reporte de Cambios")
st.caption("Seguimiento histórico de KPIs, registro de cambios y análisis antes/después por ML ID.")
st.markdown("---")

with st.container(border=True):
    c1, c2 = st.columns([3, 1])

    with c1:
        st.subheader("Módulo en desarrollo")
        st.write(
            "Este espacio estará destinado a revisar la evolución de KPIs por ML ID, "
            "registrar cambios operativos o comerciales y comparar el desempeño antes y después de cada ajuste."
        )
        st.info(
            "en desarrollo",
            icon="ℹ️",
        )

    with c2:
        st.metric("Estado", "En desarrollo")
        st.metric("Versión", "0.1")

st.markdown("### Alcance previsto")

col1, col2, col3 = st.columns(3)

with col1:
    with st.container(border=True):
        st.markdown("**1. Histórico KPIs**")
        st.write(
            "Visualización del comportamiento de cada ML ID en el tiempo."
        )

with col2:
    with st.container(border=True):
        st.markdown("**2. Registro de cambios**")
        st.write(
            "Bitácora de cambios aplicados: imagen, campaña, precios y otros ajustes."
        )

with col3:
    with st.container(border=True):
        st.markdown("**3. Antes y después**")
        st.write(
            "Evaluación comparativa de KPIs antes y después de cada cambio."
        )

st.markdown("---")
st.warning(
    "Este módulo aún se encuentra en desarrollo",
    icon="⚠️",
)
