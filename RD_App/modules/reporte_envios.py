from io import BytesIO

import pandas as pd
import streamlit as st

from services.db import fetch_all, execute


st.set_page_config(
    page_title="Reporte de Envíos",
    page_icon="🚚",
    layout="wide",
)


DIMENSION_COLUMNS = [
    "ml_id",
    "estado_meli",
    "titulo_ecom",
    "sku",
    "tipo_publicacion",
    "envio_gratis",
    "logistica",
    "precio_venta_final",
    "cuenta",
    "titulo_meli",
    "alto",
    "alto_meli",
    "largo",
    "largo_meli",
    "ancho",
    "ancho_meli",
    "peso",
    "peso_meli",
    "costo_simulado",
    "costo_envio",
    "revision",
    "valor_reclamar",
]


EDITABLE_DIMENSIONS = [
    "alto",
    "largo",
    "ancho",
    "peso",
]


FILTER_TEXT_COLUMNS = [
    "ml_id",
    "titulo_ecom",
    "sku",
    "titulo_meli",
]


FILTER_MULTI_COLUMNS = [
    "estado_meli",
    "envio_gratis",
    "logistica",
    "cuenta",
    "revision",
]


def init_state():
    defaults = {
        "envios_df_dimensiones": pd.DataFrame(),
        "envios_df_ordenes": pd.DataFrame(),
        "envios_selected_ml_id": None,
        "envios_selected_cuenta": None,
        "envios_filters_nonce": 0,
        "envios_filters": {
            "ml_id": "",
            "titulo_ecom": "",
            "sku": "",
            "titulo_meli": "",
            "estado_meli": [],
            "envio_gratis": [],
            "logistica": [],
            "cuenta": [],
            "revision": [],
        },
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def load_dimensions():
    rows = fetch_all(
        """
        SELECT *
        FROM rd_tabla_dimensiones
        """
    )

    df = pd.DataFrame(rows) if rows else pd.DataFrame()

    if not df.empty:
        for column in EDITABLE_DIMENSIONS:
            if column in df.columns:
                df[column] = pd.to_numeric(
                    df[column],
                    errors="coerce",
                )

    st.session_state.envios_df_dimensiones = df


def load_orders(ml_id):
    if not ml_id:
        st.session_state.envios_df_ordenes = pd.DataFrame()
        return

    rows = fetch_all(
        """
        SELECT *
        FROM rd_tabla_ordenes_reclamacion
        WHERE ml_id = %s
        ORDER BY ml_id
        """,
        (str(ml_id),),
    )

    st.session_state.envios_df_ordenes = (
        pd.DataFrame(rows)
        if rows
        else pd.DataFrame()
    )


def unique_options(df, column):
    if df.empty or column not in df.columns:
        return []

    values = (
        df[column]
        .dropna()
        .astype(str)
        .str.strip()
    )

    values = values[values != ""].drop_duplicates().sort_values().tolist()

    return values


def apply_filters(df):
    if df.empty:
        return df.copy()

    filters = st.session_state.envios_filters
    filtered = df.copy()

    for column in FILTER_TEXT_COLUMNS:
        value = str(filters.get(column, "") or "").strip()

        if value and column in filtered.columns:
            filtered = filtered[
                filtered[column]
                .astype(str)
                .str.contains(
                    value,
                    case=False,
                    na=False,
                )
            ]

    for column in FILTER_MULTI_COLUMNS:
        selected = filters.get(column, [])

        if selected and column in filtered.columns:
            filtered = filtered[
                filtered[column]
                .astype(str)
                .isin(selected)
            ]

    return filtered.reset_index(drop=True)


def update_filter_value(key, value):
    st.session_state.envios_filters[key] = value


def validate_integer(value, field_name):
    if value is None or pd.isna(value):
        return None

    if isinstance(value, str):
        value = value.strip()

    if value == "":
        return None

    try:
        numeric_value = float(value)
    except Exception as exc:
        raise ValueError(
            f"{field_name} debe ser un número entero."
        ) from exc

    if not numeric_value.is_integer():
        raise ValueError(
            f"{field_name} debe ser un número entero sin decimales."
        )

    integer_value = int(numeric_value)

    if integer_value < 0:
        raise ValueError(
            f"{field_name} no puede ser negativo."
        )

    return integer_value


def update_dimensions(
    ml_id,
    cuenta,
    alto,
    largo,
    ancho,
    peso,
):
    """
    Actualiza únicamente las dimensiones editables.

    La combinación ml_id + cuenta se utiliza para evitar modificar
    accidentalmente la publicación equivalente de otra cuenta.
    """
    alto_value = validate_integer(alto, "Alto")
    largo_value = validate_integer(largo, "Largo")
    ancho_value = validate_integer(ancho, "Ancho")
    peso_value = validate_integer(peso, "Peso")

    query = """
        UPDATE rd_tabla_dimensiones
        SET alto = %s,
            largo = %s,
            ancho = %s,
            peso = %s
        WHERE ml_id = %s
          AND cuenta = %s
    """

    execute(
        query,
        (
            alto_value,
            largo_value,
            ancho_value,
            peso_value,
            str(ml_id),
            str(cuenta),
        ),
    )


def dataframe_to_csv_bytes(df):
    return df.to_csv(
        index=False,
        encoding="utf-8-sig",
    ).encode("utf-8-sig")


def dataframe_to_excel_bytes(df, sheet_name):
    buffer = BytesIO()

    try:
        with pd.ExcelWriter(
            buffer,
            engine="xlsxwriter",
        ) as writer:
            df.to_excel(
                writer,
                index=False,
                sheet_name=sheet_name[:31],
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
                    sheet_name=sheet_name[:31],
                )
        except Exception:
            return None

    return buffer.getvalue()


def export_buttons(
    df,
    file_prefix,
    sheet_name,
):
    if df.empty:
        st.info("No hay información disponible para exportar.")
        return

    csv_bytes = dataframe_to_csv_bytes(df)
    excel_bytes = dataframe_to_excel_bytes(
        df,
        sheet_name,
    )

    col_csv, col_excel = st.columns(2)

    with col_csv:
        st.download_button(
            "Exportar CSV",
            data=csv_bytes,
            file_name=f"{file_prefix}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with col_excel:
        if excel_bytes is not None:
            st.download_button(
                "Exportar Excel",
                data=excel_bytes,
                file_name=f"{file_prefix}.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                use_container_width=True,
            )
        else:
            st.button(
                "Exportar Excel",
                disabled=True,
                use_container_width=True,
                help=(
                    "Instala xlsxwriter u openpyxl para habilitar "
                    "la exportación a Excel."
                ),
            )


def render_filters(df):
    st.subheader("Filtros")

    nonce = st.session_state.envios_filters_nonce
    filters = st.session_state.envios_filters

    text_col_1, text_col_2, text_col_3, text_col_4 = st.columns(4)

    with text_col_1:
        ml_id = st.text_input(
            "ML ID",
            value=filters["ml_id"],
            key=f"envios_ml_id_{nonce}",
        )
        update_filter_value("ml_id", ml_id)

    with text_col_2:
        titulo_ecom = st.text_input(
            "Título Ecom",
            value=filters["titulo_ecom"],
            key=f"envios_titulo_ecom_{nonce}",
        )
        update_filter_value("titulo_ecom", titulo_ecom)

    with text_col_3:
        sku = st.text_input(
            "SKU",
            value=filters["sku"],
            key=f"envios_sku_{nonce}",
        )
        update_filter_value("sku", sku)

    with text_col_4:
        titulo_meli = st.text_input(
            "Título Meli",
            value=filters["titulo_meli"],
            key=f"envios_titulo_meli_{nonce}",
        )
        update_filter_value("titulo_meli", titulo_meli)

    select_col_1, select_col_2, select_col_3 = st.columns(3)

    with select_col_1:
        estado_options = unique_options(
            df,
            "estado_meli",
        )

        estado_meli = st.multiselect(
            "Estado Meli",
            options=estado_options,
            default=[
                value
                for value in filters["estado_meli"]
                if value in estado_options
            ],
            key=f"envios_estado_meli_{nonce}",
        )

        update_filter_value(
            "estado_meli",
            estado_meli,
        )

    with select_col_2:
        envio_options = unique_options(
            df,
            "envio_gratis",
        )

        envio_gratis = st.multiselect(
            "Envío gratis",
            options=envio_options,
            default=[
                value
                for value in filters["envio_gratis"]
                if value in envio_options
            ],
            key=f"envios_envio_gratis_{nonce}",
        )

        update_filter_value(
            "envio_gratis",
            envio_gratis,
        )

    with select_col_3:
        logistica_options = unique_options(
            df,
            "logistica",
        )

        logistica = st.multiselect(
            "Logística",
            options=logistica_options,
            default=[
                value
                for value in filters["logistica"]
                if value in logistica_options
            ],
            key=f"envios_logistica_{nonce}",
        )

        update_filter_value(
            "logistica",
            logistica,
        )

    select_col_4, select_col_5 = st.columns(2)

    with select_col_4:
        cuenta_options = unique_options(
            df,
            "cuenta",
        )

        cuenta = st.multiselect(
            "Cuenta",
            options=cuenta_options,
            default=[
                value
                for value in filters["cuenta"]
                if value in cuenta_options
            ],
            key=f"envios_cuenta_{nonce}",
        )

        update_filter_value(
            "cuenta",
            cuenta,
        )

    with select_col_5:
        revision_options = unique_options(
            df,
            "revision",
        )

        revision = st.multiselect(
            "Revisión",
            options=revision_options,
            default=[
                value
                for value in filters["revision"]
                if value in revision_options
            ],
            key=f"envios_revision_{nonce}",
        )

        update_filter_value(
            "revision",
            revision,
        )

    st.markdown("---")

    if st.button(
        "Limpiar filtros",
        use_container_width=True,
    ):
        st.session_state.envios_filters = {
            "ml_id": "",
            "titulo_ecom": "",
            "sku": "",
            "titulo_meli": "",
            "estado_meli": [],
            "envio_gratis": [],
            "logistica": [],
            "cuenta": [],
            "revision": [],
        }

        st.session_state.envios_filters_nonce += 1
        st.rerun()


def render_dimension_editor(row, row_index):
    ml_id = row.get("ml_id", "")
    cuenta = row.get("cuenta", "")

    with st.expander(
        f"Editar dimensiones | {ml_id} | {cuenta}",
        expanded=False,
    ):
        st.caption(
            "Solo se pueden modificar alto, largo, ancho y peso. "
            "Los valores deben ser enteros sin decimales."
        )

        with st.form(
            key=f"form_dimensiones_{row_index}_{ml_id}_{cuenta}"
        ):
            col_1, col_2, col_3, col_4 = st.columns(4)

            with col_1:
                alto = st.number_input(
                    "Alto",
                    min_value=0,
                    step=1,
                    value=int(row["alto"])
                    if pd.notna(row.get("alto"))
                    else 0,
                )

            with col_2:
                largo = st.number_input(
                    "Largo",
                    min_value=0,
                    step=1,
                    value=int(row["largo"])
                    if pd.notna(row.get("largo"))
                    else 0,
                )

            with col_3:
                ancho = st.number_input(
                    "Ancho",
                    min_value=0,
                    step=1,
                    value=int(row["ancho"])
                    if pd.notna(row.get("ancho"))
                    else 0,
                )

            with col_4:
                peso = st.number_input(
                    "Peso",
                    min_value=0,
                    step=1,
                    value=int(row["peso"])
                    if pd.notna(row.get("peso"))
                    else 0,
                )

            guardar = st.form_submit_button(
                "Guardar dimensiones",
                use_container_width=True,
            )

            if guardar:
                try:
                    update_dimensions(
                        ml_id=ml_id,
                        cuenta=cuenta,
                        alto=alto,
                        largo=largo,
                        ancho=ancho,
                        peso=peso,
                    )

                    st.success(
                        f"Dimensiones actualizadas para {ml_id}."
                    )

                    load_dimensions()
                    st.rerun()

                except Exception as exc:
                    st.error(
                        f"No fue posible actualizar las dimensiones: {exc}"
                    )


def render_orders_for_record(row, row_index):
    ml_id = str(row.get("ml_id", "") or "")
    cuenta = str(row.get("cuenta", "") or "")

    if st.button(
        "Consultar órdenes",
        key=f"consultar_ordenes_{row_index}_{ml_id}_{cuenta}",
        use_container_width=True,
    ):
        st.session_state.envios_selected_ml_id = ml_id
        st.session_state.envios_selected_cuenta = cuenta
        load_orders(ml_id)

    selected_ml_id = st.session_state.get(
        "envios_selected_ml_id"
    )

    if selected_ml_id != ml_id:
        return

    st.markdown(
        f"#### Órdenes asociadas a {ml_id}"
    )

    orders_df = st.session_state.envios_df_ordenes

    if orders_df.empty:
        st.info(
            "No se encontraron órdenes de venta para este ML ID."
        )
        return

    st.dataframe(
        orders_df,
        use_container_width=True,
        hide_index=True,
    )

    export_buttons(
        df=orders_df,
        file_prefix=f"ordenes_{ml_id}",
        sheet_name="ordenes_venta",
    )


def render_dimensions_table(filtered_df):
    if filtered_df.empty:
        st.info(
            "No hay registros que coincidan con los filtros."
        )
        return

    st.subheader("Registros encontrados")

    st.metric(
        "Registros visibles",
        len(filtered_df),
    )

    visible_columns = [
        column
        for column in DIMENSION_COLUMNS
        if column in filtered_df.columns
    ]

    display_df = filtered_df[visible_columns].copy()

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### Acciones por registro")

    for row_index, (_, row) in enumerate(
        filtered_df.iterrows()
    ):
        ml_id = row.get("ml_id", "")
        cuenta = row.get("cuenta", "")
        titulo = row.get("titulo_meli", "")

        with st.container(border=True):
            header_col_1, header_col_2, header_col_3 = st.columns(
                [2, 5, 2]
            )

            with header_col_1:
                st.write(f"**ML ID:** {ml_id}")
                st.write(f"**Cuenta:** {cuenta}")

            with header_col_2:
                st.write(f"**Título:** {titulo}")
                st.write(f"**SKU:** {row.get('sku', '')}")

            with header_col_3:
                st.write(
                    f"**Revisión:** {row.get('revision', '')}"
                )

            action_col_1, action_col_2 = st.columns(2)

            with action_col_1:
                render_dimension_editor(
                    row=row,
                    row_index=row_index,
                )

            with action_col_2:
                render_orders_for_record(
                    row=row,
                    row_index=row_index,
                )


def main():
    init_state()

    st.title("Reporte de Envíos")
    st.caption(
        "Consulta, edición y seguimiento de dimensiones "
        "y órdenes asociadas."
    )

    if st.session_state.envios_df_dimensiones.empty:
        with st.spinner(
            "Cargando rd_tabla_dimensiones..."
        ):
            load_dimensions()

    dimensions_df = st.session_state.envios_df_dimensiones

    if dimensions_df.empty:
        st.warning(
            "La tabla rd_tabla_dimensiones no contiene registros."
        )
        st.stop()

    render_filters(dimensions_df)

    filtered_df = apply_filters(dimensions_df)

    st.subheader("Exportar dimensiones filtradas")

    export_buttons(
        df=filtered_df,
        file_prefix="reporte_envios_dimensiones",
        sheet_name="dimensiones",
    )

    st.markdown("---")

    render_dimensions_table(filtered_df)


main()
