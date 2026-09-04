from io import BytesIO

import pandas as pd
import streamlit as st


from services.db import fetch_all


st.set_page_config(
    page_title="Tablero de alertamientos",
    page_icon="🚨",
    layout="wide",
)


TABLE_NAME = "rd_tabla_alertamientos"

TEXT_FILTERS = [
    ("ml_id", "ML ID"),
    ("titulo_ecom", "Título Ecom"),
    ("sku", "SKU"),
    ("ml_id_sincronizados", "ML ID sincronizados"),
    ("titulo_meli", "Título Meli"),
]

SELECT_FILTERS = [
    (
        "estado_meli",
        "Estado Meli",
    ),
    (
        "relacion_catalogo_tradicional",
        "Relación catálogo tradicional",
    ),
    (
        "envio_gratis",
        "Envío gratis",
    ),
    (
        "logistica",
        "Logística",
    ),
    (
        "cuenta",
        "Cuenta",
    ),
    (
        "tipo_oferta",
        "Tipo de oferta",
    ),
    (
        "marca_producto",
        "Marca producto",
    ),
]

DISPLAY_COLUMN_NAMES = {
    "ml_id": "ML ID",
    "estado_meli": "Estado Meli",
    "titulo_ecom": "Título Ecom",
    "sku": "SKU",
    "ml_id_sincronizados": "ML ID sincronizados",
    "relacion_catalogo_tradicional": "Relación catálogo tradicional",
    "envio_gratis": "Envío gratis",
    "logistica": "Logística",
    "cuenta": "Cuenta",
    "titulo_meli": "Título Meli",
    "permalink": "Enlace Mercado Libre",
    "tipo_oferta": "Tipo de oferta",
    "marca_producto": "Marca producto",
    "alerta_promocion": "Alerta promoción",
    "alerta_cuotas": "Alerta cuotas",
    "alerta_publicidad": "Alerta publicidad",
}

ALERTA_COLORS = [
    "#ff4b4b",
    "#f59e0b",
    "#3b82f6",
    "#8b5cf6",
    "#10b981",
    "#ec4899",
]


def init_state():
    defaults = {
        "alertamientos_df_base": pd.DataFrame(),
        "alertamientos_filters_nonce": 0,
        "alertamientos_filters": {},
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def normalizar_dataframe(df):
    """
    Normaliza tipos de texto para que filtros y conteos no fallen
    cuando una columna contiene valores nulos.
    """
    if df.empty:
        return df.copy()

    df = df.copy()

    for column in df.columns:
        if df[column].dtype == "object":
            df[column] = df[column].fillna("").astype(str).str.strip()

    return df


def load_alertamientos():
    """
    Consulta la tabla completa de alertamientos.
    """
    rows = fetch_all(
        f"""
        SELECT *
        FROM {TABLE_NAME}
        """
    )

    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    df = normalizar_dataframe(df)

    st.session_state.alertamientos_df_base = df.copy()


def get_alert_columns(df):
    """
    Detecta todas las columnas de alertas disponibles.

    Ejemplos:
    - alerta_promocion
    - alerta_cuotas
    - alerta_publicidad
    - alerta_otra_futura
    """
    if df.empty:
        return []

    return [
        column
        for column in df.columns
        if str(column).lower().startswith("alerta_")
    ]


def format_alert_name(column):
    """
    Convierte alerta_promocion en Alerta promoción.
    """
    return (
        str(column)
        .replace("_", " ")
        .strip()
        .title()
    )


def get_unique_options(df, column):
    """
    Retorna valores únicos, limpios y ordenados para filtros selectbox.
    """
    if df.empty or column not in df.columns:
        return []

    values = (
        df[column]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    values = values[values != ""].drop_duplicates().sort_values().tolist()

    return values


def get_filter_defaults():
    """
    Genera el diccionario base de filtros.
    """
    defaults = {}

    for column, _ in TEXT_FILTERS:
        defaults[column] = ""

    for column, _ in SELECT_FILTERS:
        defaults[column] = "Todos"

    return defaults


def ensure_filters_initialized(df):
    """
    Inicializa filtros incluyendo las alertas detectadas dinámicamente.
    """
    current_filters = st.session_state.get(
        "alertamientos_filters",
        {},
    )

    defaults = get_filter_defaults()

    for alert_column in get_alert_columns(df):
        defaults[alert_column] = "Todos"

    for key, value in defaults.items():
        if key not in current_filters:
            current_filters[key] = value

    st.session_state.alertamientos_filters = current_filters


def reset_filters(df):
    """
    Restablece todos los filtros y crea claves nuevas para widgets.
    """
    filters = get_filter_defaults()

    for alert_column in get_alert_columns(df):
        filters[alert_column] = "Todos"

    st.session_state.alertamientos_filters = filters
    st.session_state.alertamientos_filters_nonce += 1


def apply_filters(df):
    """
    Aplica filtros de texto y filtros tipo selectbox.

    Todos los filtros trabajan sobre los datos ya consultados desde SQL,
    por lo que el tablero, gráficos y exportaciones se actualizan
    dinámicamente sin hacer una nueva consulta SQL por cada interacción.
    """
    if df.empty:
        return df.copy()

    ensure_filters_initialized(df)

    filters = st.session_state.alertamientos_filters
    filtered_df = df.copy()

    for column, _label in TEXT_FILTERS:
        search_value = str(
            filters.get(column, "")
        ).strip()

        if (
            search_value
            and column in filtered_df.columns
        ):
            filtered_df = filtered_df[
                filtered_df[column]
                .astype(str)
                .str.contains(
                    search_value,
                    case=False,
                    na=False,
                )
            ]

    select_columns = [
        column
        for column, _label in SELECT_FILTERS
    ]

    select_columns.extend(
        get_alert_columns(df)
    )

    for column in select_columns:
        selected_value = str(
            filters.get(column, "Todos")
        ).strip()

        if (
            selected_value
            and selected_value != "Todos"
            and column in filtered_df.columns
        ):
            filtered_df = filtered_df[
                filtered_df[column]
                .astype(str)
                == selected_value
            ]

    return filtered_df.reset_index(drop=True)


def dataframe_to_csv_bytes(df):
    """
    Convierte un DataFrame a CSV UTF-8 con BOM para Excel.
    """
    return df.to_csv(
        index=False,
        encoding="utf-8-sig",
    ).encode("utf-8-sig")


def dataframe_to_excel_bytes(df):
    """
    Genera Excel con una hoja de datos y una hoja de resumen por alertas.
    """
    buffer = BytesIO()

    try:
        with pd.ExcelWriter(
            buffer,
            engine="xlsxwriter",
        ) as writer:
            df.to_excel(
                writer,
                index=False,
                sheet_name="alertamientos",
            )

            resumen_df = build_alert_summary_table(df)

            resumen_df.to_excel(
                writer,
                index=False,
                sheet_name="resumen_alertas",
            )

            workbook = writer.book

            header_format = workbook.add_format(
                {
                    "bold": True,
                    "bg_color": "#1F2937",
                    "font_color": "#FFFFFF",
                    "border": 1,
                }
            )

            number_format = workbook.add_format(
                {
                    "num_format": "#,##0",
                }
            )

            for sheet_name, current_df in [
                ("alertamientos", df),
                ("resumen_alertas", resumen_df),
            ]:
                worksheet = writer.sheets[sheet_name]

                for col_num, column_name in enumerate(
                    current_df.columns
                ):
                    worksheet.write(
                        0,
                        col_num,
                        column_name,
                        header_format,
                    )

                    max_len = max(
                        len(str(column_name)),
                        current_df[column_name]
                        .fillna("")
                        .astype(str)
                        .str.len()
                        .max()
                        if not current_df.empty
                        else 0,
                    )

                    width = min(max_len + 2, 60)
                    worksheet.set_column(
                        col_num,
                        col_num,
                        width,
                    )

                if "Cantidad" in current_df.columns:
                    qty_column = current_df.columns.get_loc(
                        "Cantidad"
                    )
                    worksheet.set_column(
                        qty_column,
                        qty_column,
                        14,
                        number_format,
                    )

    except Exception:
        try:
            with pd.ExcelWriter(
                buffer,
                engine="openpyxl",
            ) as writer:
                df.to_excel(
                    writer,
                    index=False,
                    sheet_name="alertamientos",
                )

                resumen_df = build_alert_summary_table(df)

                resumen_df.to_excel(
                    writer,
                    index=False,
                    sheet_name="resumen_alertas",
                )
        except Exception:
            return None

    return buffer.getvalue()


def build_alert_summary_table(df):
    """
    Crea un resumen tabular de todas las alertas y sus estados.
    """
    alert_columns = get_alert_columns(df)

    rows = []

    for alert_column in alert_columns:
        alert_name = format_alert_name(alert_column)

        if df.empty:
            rows.append(
                {
                    "Alerta": alert_name,
                    "Estado": "Sin datos",
                    "Cantidad": 0,
                    "Participación %": 0,
                }
            )
            continue

        counts = (
            df[alert_column]
            .fillna("Sin dato")
            .replace("", "Sin dato")
            .astype(str)
            .value_counts(dropna=False)
        )

        total = int(counts.sum())

        for state, quantity in counts.items():
            participation = (
                round((int(quantity) / total) * 100, 2)
                if total > 0
                else 0
            )

            rows.append(
                {
                    "Alerta": alert_name,
                    "Estado": str(state),
                    "Cantidad": int(quantity),
                    "Participación %": participation,
                }
            )

    if not rows:
        return pd.DataFrame(
            columns=[
                "Alerta",
                "Estado",
                "Cantidad",
                "Participación %",
            ]
        )

    return pd.DataFrame(rows)


def render_pie_chart(counts, chart_key, title):
    """
    Genera un gráfico circular dinámico de participación por estado.
    """
    if counts.empty:
        st.caption("Sin datos para graficar.")
        return

    chart_df = pd.DataFrame(
        {
            "Estado": counts.index.astype(str),
            "Cantidad": counts.values,
        }
    )

    try:
        import plotly.express as px

        fig = px.pie(
            chart_df,
            names="Estado",
            values="Cantidad",
            hole=0.48,
            color_discrete_sequence=ALERTA_COLORS,
        )

        fig.update_traces(
            textposition="inside",
            textinfo="percent+label",
            hovertemplate=(
                "<b>%{label}</b><br>"
                "Publicaciones: %{value}<br>"
                "Participación: %{percent}<extra></extra>"
            ),
        )

        fig.update_layout(
            title={
                "text": title,
                "x": 0.5,
                "xanchor": "center",
            },
            showlegend=False,
            margin={
                "l": 10,
                "r": 10,
                "t": 48,
                "b": 10,
            },
            height=260,
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            key=chart_key,
        )

    except Exception:
        st.bar_chart(
            chart_df.set_index("Estado"),
            use_container_width=True,
        )


def render_alert_card(df, alert_column, position):
    """
    Presenta un bloque por alerta con:
    - total de publicaciones;
    - tabla de estados;
    - gráfico circular de participación.
    """
    alert_name = format_alert_name(alert_column)

    with st.container(border=True):
        st.markdown(
            f"### {alert_name}"
        )

        if df.empty:
            st.metric(
                "Publicaciones filtradas",
                0,
            )
            st.caption(
                "No hay publicaciones con los filtros actuales."
            )
            return

        states = (
            df[alert_column]
            .fillna("Sin dato")
            .replace("", "Sin dato")
            .astype(str)
        )

        counts = states.value_counts(dropna=False)
        total = int(counts.sum())

        st.metric(
            "Publicaciones filtradas",
            total,
        )

        detail_rows = []

        for state, quantity in counts.items():
            share = (
                round((int(quantity) / total) * 100, 2)
                if total > 0
                else 0
            )

            detail_rows.append(
                {
                    "Estado": str(state),
                    "Cantidad": int(quantity),
                    "Participación": f"{share:.2f}%",
                }
            )

        states_df = pd.DataFrame(detail_rows)

        st.dataframe(
            states_df,
            hide_index=True,
            use_container_width=True,
        )

        render_pie_chart(
            counts=counts,
            chart_key=f"pie_{alert_column}_{position}",
            title=f"Participación · {alert_name}",
        )


def render_alert_dashboard(filtered_df):
    """
    Dibuja el tablero de alertas en una distribución de columnas.
    """
    alert_columns = get_alert_columns(filtered_df)

    if not alert_columns:
        st.info(
            "No se encontraron columnas de alertas. "
            "Las columnas deben iniciar con el prefijo alerta_."
        )
        return

    st.subheader("Resumen de alertamientos")
    st.caption(
        "Los conteos y gráficos se actualizan automáticamente "
        "según los filtros aplicados."
    )

    total_publicaciones = len(filtered_df)
    total_alertas = len(alert_columns)

    metric_1, metric_2 = st.columns(2)

    with metric_1:
        st.metric(
            "Publicaciones filtradas",
            total_publicaciones,
        )

    with metric_2:
        st.metric(
            "Tipos de alerta analizados",
            total_alertas,
        )

    for start in range(0, len(alert_columns), 3):
        row_alerts = alert_columns[start:start + 3]
        columns = st.columns(len(row_alerts))

        for position, alert_column in enumerate(row_alerts):
            with columns[position]:
                render_alert_card(
                    df=filtered_df,
                    alert_column=alert_column,
                    position=start + position,
                )


def render_filters(df):
    """
    Renderiza los filtros superiores.
    """
    ensure_filters_initialized(df)

    filters = st.session_state.alertamientos_filters
    nonce = st.session_state.alertamientos_filters_nonce

    st.subheader("Filtros")

    text_columns = st.columns(3)

    for index, (column, label) in enumerate(TEXT_FILTERS):
        column_container = text_columns[index % 3]

        with column_container:
            current_value = st.text_input(
                label,
                value=filters.get(column, ""),
                key=f"alertamientos_{column}_{nonce}",
                placeholder=f"Buscar por {label.lower()}...",
            )

            st.session_state.alertamientos_filters[
                column
            ] = current_value

    st.markdown("#### Datos de publicación")

    select_columns = st.columns(3)

    for index, (column, label) in enumerate(SELECT_FILTERS):
        options = ["Todos"] + get_unique_options(
            df,
            column,
        )

        current_value = filters.get(
            column,
            "Todos",
        )

        if current_value not in options:
            current_value = "Todos"

        with select_columns[index % 3]:
            selected_value = st.selectbox(
                label,
                options=options,
                index=options.index(current_value),
                key=f"alertamientos_{column}_{nonce}",
            )

            st.session_state.alertamientos_filters[
                column
            ] = selected_value

    alert_columns = get_alert_columns(df)

    if alert_columns:
        st.markdown("#### Filtros por alertas")

        alert_filter_columns = st.columns(
            min(len(alert_columns), 3)
        )

        for index, alert_column in enumerate(alert_columns):
            options = ["Todos"] + get_unique_options(
                df,
                alert_column,
            )

            current_value = filters.get(
                alert_column,
                "Todos",
            )

            if current_value not in options:
                current_value = "Todos"

            with alert_filter_columns[
                index % len(alert_filter_columns)
            ]:
                selected_value = st.selectbox(
                    format_alert_name(alert_column),
                    options=options,
                    index=options.index(current_value),
                    key=f"alertamientos_{alert_column}_{nonce}",
                )

                st.session_state.alertamientos_filters[
                    alert_column
                ] = selected_value

    st.markdown("---")

    action_col_1, action_col_2, action_col_3 = st.columns(
        [1, 1, 2]
    )

    with action_col_1:
        if st.button(
            "Limpiar filtros",
            use_container_width=True,
        ):
            reset_filters(df)
            st.rerun()

    with action_col_2:
        if st.button(
            "Actualizar datos",
            use_container_width=True,
        ):
            with st.spinner(
                "Actualizando información..."
            ):
                load_alertamientos()

            reset_filters(
                st.session_state.alertamientos_df_base
            )

            st.success(
                "Información actualizada correctamente."
            )

            st.rerun()

    with action_col_3:
        st.caption(
            "Los filtros se aplican automáticamente sobre "
            "los datos disponibles en pantalla."
        )


def render_exports(filtered_df):
    """
    Agrega exportación del resultado filtrado en CSV y Excel.
    """
    st.subheader("Exportar información filtrada")

    if filtered_df.empty:
        st.info(
            "No hay registros filtrados para exportar."
        )
        return

    csv_bytes = dataframe_to_csv_bytes(filtered_df)
    excel_bytes = dataframe_to_excel_bytes(filtered_df)

    col_csv, col_excel, col_info = st.columns(
        [1, 1, 2]
    )

    with col_csv:
        st.download_button(
            "Descargar CSV",
            data=csv_bytes,
            file_name="tablero_alertamientos_filtrado.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with col_excel:
        if excel_bytes is not None:
            st.download_button(
                "Descargar Excel",
                data=excel_bytes,
                file_name="tablero_alertamientos_filtrado.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                use_container_width=True,
            )
        else:
            st.button(
                "Descargar Excel",
                disabled=True,
                use_container_width=True,
                help=(
                    "No fue posible generar el archivo Excel. "
                    "Verifica que openpyxl o xlsxwriter estén instalados."
                ),
            )

    with col_info:
        st.caption(
            f"Se exportarán {len(filtered_df):,} publicaciones "
            "con todos los campos disponibles en la tabla."
        )


def render_main_table(filtered_df):
    """
    Muestra todos los campos de la tabla de alertamientos.
    """
    st.subheader("Detalle de publicaciones")

    if filtered_df.empty:
        st.info(
            "No hay publicaciones que coincidan con los filtros aplicados."
        )
        return

    display_df = filtered_df.copy()

    existing_columns = [
        column
        for column in DISPLAY_COLUMN_NAMES
        if column in display_df.columns
    ]

    other_columns = [
        column
        for column in display_df.columns
        if column not in existing_columns
    ]

    display_df = display_df[
        existing_columns + other_columns
    ].copy()

    display_df = display_df.rename(
        columns={
            column: DISPLAY_COLUMN_NAMES.get(
                column,
                column,
            )
            for column in display_df.columns
        }
    )

    column_config = {}

    if "Enlace Mercado Libre" in display_df.columns:
        column_config["Enlace Mercado Libre"] = (
            st.column_config.LinkColumn(
                "Enlace Mercado Libre",
                display_text="Abrir publicación",
            )
        )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
        height=650,
    )


def main():
    init_state()

    st.title("Tablero de alertamientos")
    st.caption(
        "Vista consolidada de alertas comerciales, promocionales, "
        "de cuotas y publicidad."
    )

    if st.session_state.alertamientos_df_base.empty:
        with st.spinner(
            "Cargando información de alertamientos..."
        ):
            load_alertamientos()

    df_base = st.session_state.alertamientos_df_base

    if df_base.empty:
        st.warning(
            "La tabla rd_tabla_alertamientos no contiene registros."
        )
        st.stop()

    render_filters(df_base)

    filtered_df = apply_filters(df_base)

    st.markdown("---")

    render_alert_dashboard(filtered_df)

    st.markdown("---")

    render_exports(filtered_df)

    st.markdown("---")

    render_main_table(filtered_df)


main()
