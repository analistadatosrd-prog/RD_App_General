import streamlit as st

from services.reviews_data import (
    ReviewFilters,
    get_dashboard_metrics,
    get_date_bounds,
    get_filter_options,
)


def run():
    st.title("Diagnóstico de Reviews")

    try:
        fecha_minima, fecha_maxima = get_date_bounds()
        options = get_filter_options()
        metrics = get_dashboard_metrics(ReviewFilters())

        st.success("Conexión y consultas base correctas.")
        st.write("Rango de fechas:", fecha_minima, "→", fecha_maxima)
        st.write("Opciones de filtro:", options)
        st.write("Métricas sin filtros:", metrics)

    except Exception as exc:
        st.error("Falló la capa de datos.")
        st.exception(exc)


if __name__ == "__main__":
    run()
