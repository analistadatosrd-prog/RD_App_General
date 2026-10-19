from __future__ import annotations

import math
from decimal import Decimal, ROUND_CEILING
import html

import pandas as pd
import streamlit as st

from services.db import fetch_all
from services.ecom_client import build_outputs, fetch_ml_listings_fast, fetch_products_fast

IVA_PAIS = {"AR": 0.21, "CL": 0.19, "MX": 0.16}
MONEDA = {"AR": "ARS", "CL": "CLP", "MX": "MXN"}
# Tasas heredadas del módulo original; no se presuponen vigentes por país.
CAMPAIGN_CUOTAS = {
    "Sin cuotas": 0.0, "3 cuotas": 0.084, "6 cuotas": 0.123,
    "9 cuotas": 0.157, "12 cuotas": 0.192,
}
# Límites inferiores inclusivos: [inicio, siguiente inicio).
# Las etiquetas se conservan exactamente como en rd_tabla_costos.
RANGOS_ENVIO = {
    "AR": [(0, "Hasta $32.999"), (33000, "De $ 33.000 a $ 49.999"),
           (50000, "Más de $ 50.000")],
    "CL": [(0, "Hasta $9.989"), (9990, "De $9.990 a $19.989"),
           (19990, "Desde $19.990")],
    "MX": [(0, "De $0 a $98,99"), (99, "De $99 a $198,99"),
           (199, "De $199 a $298,99"), (299, "De $299 a $498,99"),
           (499, "De $499 a $998,99"), (999, "Desde $999")],
}
RANGOS_UNIDAD_AR = [(0, "Hasta $14.999"), (15000, "De $15.000 a $23.999"),
                    (24000, "De $24.000 a $32.999"), (33000, "No Aplica")]


def numero(value, campo, default=None):
    if value is None or pd.isna(value):
        if default is not None:
            return float(default)
        raise ValueError(f"Falta el dato numérico: {campo}.")
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Dato no numérico: {campo}.") from exc
    if not math.isfinite(result):
        raise ValueError(f"Dato no finito: {campo}.")
    return result


def pais_producto(producto):
    value = producto.get("country_code")
    country = "" if value is None or pd.isna(value) else str(value).strip().upper()
    if country not in IVA_PAIS:
        raise ValueError("country_code debe ser AR, CL o MX; no se infiere por cuenta o ML ID.")
    return country


def clasificar(precio, rangos):
    precio = numero(precio, "precio")
    if precio < 0:
        raise ValueError("El precio no puede ser negativo.")
    return next(label for lower, label in reversed(rangos) if precio >= lower)


def clasificar_rango_envio(precio, country_code):
    return clasificar(precio, RANGOS_ENVIO[country_code])


def clasificar_rango_und(precio, country_code):
    return clasificar(precio, RANGOS_UNIDAD_AR) if country_code == "AR" else "No Aplica"


def cargar_tarifas():
    rows = fetch_all('''
        SELECT country_code, rango_peso_facturable,
               rango_valor_costo_envio, costo_envio,
               rango_valor_costo_und_vendida, "Costo_por_unidad_vendida"
        FROM rd_tabla_costos
    ''')
    df = pd.DataFrame(rows or [])
    if df.empty:
        raise ValueError("rd_tabla_costos no tiene tarifas.")
    for col in ["country_code", "rango_peso_facturable", "rango_valor_costo_envio",
                "rango_valor_costo_und_vendida"]:
        df[col] = df[col].fillna("").astype(str).str.strip()
    df["country_code"] = df["country_code"].str.upper()
    return df


def buscar_tarifa(tarifas, country, peso, columna_rango, rango, columna_costo):
    peso = "" if peso is None or pd.isna(peso) else str(peso).strip()
    mask = ((tarifas["country_code"] == country)
            & (tarifas["rango_peso_facturable"] == peso)
            & (tarifas[columna_rango] == rango))
    rows = tarifas.loc[mask, columna_costo]
    if rows.empty:
        raise ValueError(f"No hay tarifa: {country}, peso '{peso}', rango '{rango}'.")
    values = pd.to_numeric(rows, errors="coerce")
    if values.isna().any() or not all(math.isfinite(float(x)) for x in values):
        raise ValueError(f"Tarifa inválida: {country}, {peso}, {rango}.")
    unique = values.unique()
    if len(unique) != 1 or unique[0] < 0:
        raise ValueError(f"Tarifas contradictorias o negativas: {country}, {peso}, {rango}.")
    return float(unique[0])


def calcular_rentabilidad(producto, precio_sim, pct_cuotas, incluir_envio, tarifas):
    country = pais_producto(producto)
    precio = numero(precio_sim, "precio simulado")
    costo = numero(producto.get("costo_fijo_ecom"), "costo_fijo_ecom")
    venta = numero(producto.get("pct_costo_venta"), "pct_costo_venta")
    cuotas = numero(pct_cuotas, "pct_cuotas")
    if precio < 0 or costo <= 0 or not 0 <= venta < 1 or not 0 <= cuotas < 1:
        raise ValueError("Se requiere costo mayor que cero, precio no negativo y tasas decimales entre 0 y 1.")
    factor = 1 + IVA_PAIS[country]
    peso = producto.get("rango_peso_facturable")
    rango_envio = clasificar_rango_envio(precio, country)
    rango_und = clasificar_rango_und(precio, country)
    envio = buscar_tarifa(tarifas, country, peso, "rango_valor_costo_envio",
                          rango_envio, "costo_envio") if incluir_envio else 0.0
    unidad = buscar_tarifa(tarifas, country, peso, "rango_valor_costo_und_vendida",
                           rango_und, "Costo_por_unidad_vendida") if rango_und != "No Aplica" else 0.0
    iva = precio - precio / factor
    costo_cuotas = cuotas * precio
    comision = venta * precio
    costo_venta = costo_cuotas + comision + unidad
    renta = precio / factor - costo - envio / factor - costo_venta / factor
    return {
        "country_code": country, "moneda": MONEDA[country],
        "precio_venta_final_sim": precio, "costo_fijo_sim": costo,
        "valor_iva_sim": iva, "iva_pct_sim": IVA_PAIS[country] * 100,
        "costo_envio_sim": envio, "costo_und_vendida_sim": unidad,
        "pct_costo_venta_sim": venta * 100, "pct_costo_cuotas_sim": cuotas * 100,
        "costo_cuotas_sim": costo_cuotas, "costo_comision_sim": comision,
        "costo_venta_sim": costo_venta, "rentabilidad_sim": renta,
        "pct_rentabilidad_sim": renta / costo * 100,
        "rango_envio_sim": rango_envio, "rango_und_sim": rango_und,
    }


def simular_escenario_2(producto, pct_obj, pct_cuotas, incluir_envio, tarifas):
    country = pais_producto(producto)
    costo = numero(producto.get("costo_fijo_ecom"), "costo_fijo_ecom")
    venta = numero(producto.get("pct_costo_venta"), "pct_costo_venta")
    target_pct = numero(pct_obj, "rentabilidad objetivo")
    if costo <= 0 or target_pct < 0 or not 0 <= venta < 1 or not 0 <= pct_cuotas < 1:
        raise ValueError("Costo, objetivo o tasas inválidos.")
    factor = 1 + IVA_PAIS[country]
    a = (1 - venta - pct_cuotas) / factor
    if a <= 0:
        raise ValueError("No existe solución creciente: comisión más cuotas alcanza o supera el 100%.")
    target = costo * target_pct / 100
    limites = {float(x[0]) for x in RANGOS_ENVIO[country]}
    if country == "AR":
        limites.update(float(x[0]) for x in RANGOS_UNIDAD_AR)
    limites = sorted(limites)
    candidates, errors = [], []
    for i, low in enumerate(limites):
        high = limites[i + 1] if i + 1 < len(limites) else math.inf
        try:
            r = calcular_rentabilidad(producto, low, pct_cuotas, incluir_envio, tarifas)
            b = costo + (r["costo_envio_sim"] + r["costo_und_vendida_sim"]) / factor
            raw = max(low, (target + b) / a)
            cents = (Decimal(str(raw)) * 100).to_integral_value(rounding=ROUND_CEILING)
            price = float(cents / 100)
            if price >= high:
                continue
            result = calcular_rentabilidad(producto, price, pct_cuotas, incluir_envio, tarifas)
            if result["rentabilidad_sim"] + 1e-8 < target:
                price = round(price + 0.01, 2)
                if price >= high:
                    continue
                result = calcular_rentabilidad(producto, price, pct_cuotas, incluir_envio, tarifas)
            if result["rentabilidad_sim"] + 1e-8 >= target:
                candidates.append(price)
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        raise ValueError("No se puede garantizar el precio mínimo por tarifas faltantes o inválidas. " + errors[0])
    if not candidates:
        raise ValueError("No se encontró precio que alcance la rentabilidad objetivo.")
    return min(candidates)


def fmt(value):
    if value is None or pd.isna(value):
        return "N/D"
    return f"$ {float(value):,.2f}"


def normalizar_dataframe(df):
    df = df.copy()
    for source, dest in [("sku_asociados", "sku"), ("skus_asociados", "sku"),
                          ("titulo_producto", "titulo_ecom")]:
        if dest not in df and source in df:
            df[dest] = df[source]
    for col in ["ml_id", "cuenta", "sku", "titulo_ecom", "country_code"]:
        if col not in df:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str).str.strip()
    df["country_code"] = df["country_code"].str.upper()
    df["costo_fijo_ecom_antiguo"] = df["costo_fijo_ecom"]
    df["costo_fijo_ecom_nuevo"] = float("nan")
    df["_roi_key"] = [str(i) for i in range(len(df))]
    return df


def actualizar_costos(df, session):
    if session is None:
        raise ValueError("Falta la sesión de EcomExperts.")
    listings = fetch_ml_listings_fast(session, None)
    products = fetch_products_fast(session, None)
    _, costs = build_outputs(listings, products, None)
    if costs.empty:
        raise ValueError("EcomExperts no devolvió costos; no se actualizó nada.")
    if not {"cuenta", "mla", "costo_total_mla"}.issubset(costs.columns):
        raise ValueError("build_outputs debe devolver cuenta, mla y costo_total_mla.")
    costs = costs[["cuenta", "mla", "costo_total_mla"]].rename(
        columns={"mla": "ml_id", "costo_total_mla": "_costo_importado"})
    for col in ["cuenta", "ml_id"]:
        costs[col] = costs[col].fillna("").astype(str).str.strip()
    if costs.duplicated(["cuenta", "ml_id"]).any():
        raise ValueError("Costos duplicados por cuenta + ML ID; se canceló el cruce.")
    result = df.merge(costs, on=["cuenta", "ml_id"], how="left", validate="many_to_one")
    new = pd.to_numeric(result.pop("_costo_importado"), errors="coerce")
    valid = new.notna() & (new > 0)
    result.loc[valid, "costo_fijo_ecom_nuevo"] = new[valid]
    result.loc[valid, "costo_fijo_ecom"] = new[valid]
    return result, int(valid.sum())


def mostrar_comparativo(producto, sim, nombre_campania=""):
    country = sim["country_code"]
    st.markdown(f"### {producto.get('ml_id', '')} · {country} / {MONEDA[country]}")
    st.write(producto.get("titulo_ecom", ""))
    left, right = st.columns(2)
    with left:
        st.subheader("Base PostgreSQL / costo vigente en sesión")
        st.write("Precio base:", fmt(producto.get("precio_venta_final")))
        st.write("Costo original:", fmt(producto.get("costo_fijo_ecom_antiguo")))
        st.write("Costo vigente para simular:", fmt(producto.get("costo_fijo_ecom")))
        st.write("Rentabilidad histórica:", fmt(producto.get("rentabilidad")))
        pct = producto.get("pct_rentabilidad")
        st.write("ROI histórico:", "N/D" if pct is None or pd.isna(pct) else f"{float(pct)*100:.2f}%")
        st.caption("La rentabilidad histórica se conserva como referencia; no se recalcula al importar costos.")
    with right:
        st.subheader("Simulación sin descuentos ni devoluciones")
        st.metric(f"Precio ({MONEDA[country]})", fmt(sim["precio_venta_final_sim"]))
        st.metric("Rentabilidad", fmt(sim["rentabilidad_sim"]))
        st.metric("ROI sobre costo", f"{sim['pct_rentabilidad_sim']:.2f}%")
        st.write(f"IVA país: {sim['iva_pct_sim']:.0f}% · {nombre_campania}")
    rows = [
        ("Costo producto", sim["costo_fijo_sim"]), ("IVA venta", sim["valor_iva_sim"]),
        ("Envío bruto", sim["costo_envio_sim"]), ("Comisión bruta", sim["costo_comision_sim"]),
        ("Cuotas bruto", sim["costo_cuotas_sim"]),
        ("Cargo por unidad bruto (solo AR)", sim["costo_und_vendida_sim"]),
        ("Costo venta bruto total", sim["costo_venta_sim"]),
    ]
    st.dataframe(pd.DataFrame(rows, columns=["Concepto", "Importe"]), hide_index=True, use_container_width=True)
    st.caption(f"Rango envío: {sim['rango_envio_sim']} · Rango unidad: {sim['rango_und_sim']}")


def main():
    st.title("Simulador ROI · AR / CL / MX")
    st.caption("IVA por país y tarifas de rd_tabla_costos. Solo lectura: no modifica PostgreSQL.")
    st.info("Supuesto de cálculo: precio y cargos de envío/venta incluyen el IVA del país; "
            "el costo del producto ya está expresado en la base neta utilizada por el simulador.")
    if not st.session_state.get("authenticated"):
        st.error("No hay una sesión autenticada de EcomExperts.")
        st.stop()
    if "roi_base_v2" not in st.session_state:
        st.session_state.roi_base_v2 = pd.DataFrame()
    c1, c2 = st.columns(2)
    reload_db = c1.button("Recargar base y tarifas desde PostgreSQL", use_container_width=True)
    update_ecom = c2.button("Actualizar costos desde sesión EcomExperts", use_container_width=True)
    if reload_db or st.session_state.roi_base_v2.empty:
        try:
            with st.spinner("Cargando publicaciones y tarifas…"):
                data = pd.DataFrame(fetch_all("SELECT * FROM rd_tabla_rentas") or [])
                if data.empty:
                    st.warning("rd_tabla_rentas está vacía.")
                    return
                normalized = normalizar_dataframe(data)
                tariffs = cargar_tarifas()
                st.session_state.roi_base_v2 = normalized
                st.session_state.roi_tarifas_v2 = tariffs
                st.session_state.pop("roi_results_v2", None)
                st.session_state.pop("roi_select_v2", None)
        except Exception as exc:
            st.error(f"No se pudo cargar: {exc}")
            return
    if update_ecom:
        try:
            with st.spinner("Consultando costos disponibles en la sesión EcomExperts…"):
                updated, count = actualizar_costos(st.session_state.roi_base_v2,
                                                    st.session_state.get("ecom_session"))
                st.session_state.roi_base_v2 = updated
                st.session_state.pop("roi_results_v2", None)
            st.success(f"Costos actualizados en {count} filas; las demás conservan su costo vigente.")
            st.caption("Solo se consultan las cuentas accesibles por esta sesión; no inicia sesiones adicionales de Chile/México.")
        except Exception as exc:
            st.error(f"No se actualizaron costos: {exc}")
    df = st.session_state.roi_base_v2
    st.subheader("Filtros")
    a, b, c, d = st.columns(4)
    country = a.selectbox("País", ["Todos"] + sorted(df.country_code.unique().tolist()))
    cuenta = b.selectbox("Cuenta", ["Todas"] + sorted(df.cuenta.unique().tolist()))
    ml = c.text_input("ML ID contiene")
    sku = d.text_input("SKU contiene")
    titulo = st.text_input("Título contiene")
    vista = df.copy()
    for column, value in [("country_code", country), ("cuenta", cuenta)]:
        if value not in ("Todos", "Todas"):
            vista = vista[vista[column] == value]
    for column, value in [("ml_id", ml), ("sku", sku), ("titulo_ecom", titulo)]:
        if value.strip():
            vista = vista[vista[column].str.contains(value.strip(), case=False, regex=False, na=False)]
    for column, label in [("estado_meli", "Estado"), ("tipo_publicacion", "Tipo publicación"),
                           ("logistica", "Logística")]:
        if column in vista:
            options = sorted(vista[column].dropna().astype(str).unique().tolist())
            chosen = st.selectbox(label, ["Todos"] + options, key=f"roi_filter_{column}")
            if chosen != "Todos":
                vista = vista[vista[column].astype(str) == chosen]
    envio_filter = st.selectbox("Envío gratis actual", ["Todos", "Sí", "No"])
    if envio_filter != "Todos" and "envio_gratis" in vista:
        vista = vista[vista.envio_gratis == (envio_filter == "Sí")]
    limit = st.selectbox("Filas visibles (no limita selección)", [50, 100, 200, 500, 1000], index=2)
    st.caption(f"{len(vista):,} filas filtradas; {min(limit, len(vista)):,} visibles.")
    st.dataframe(vista.drop(columns=["_roi_key"]).head(limit), hide_index=True, use_container_width=True)
    if vista.empty:
        return
    lookup = vista.set_index("_roi_key").to_dict(orient="index")
    valid_keys = list(lookup)
    existing = st.session_state.get("roi_select_v2", [])
    st.session_state.roi_select_v2 = [x for x in existing if x in lookup]
    s1, s2 = st.columns(2)
    if s1.button("Seleccionar todas las filtradas"):
        st.session_state.roi_select_v2 = valid_keys
    if s2.button("Deseleccionar todas"):
        st.session_state.roi_select_v2 = []
    selected = st.multiselect("Publicaciones a simular", options=valid_keys, key="roi_select_v2",
        format_func=lambda key: f"{lookup[key]['country_code']} | {lookup[key]['cuenta']} | "
                                f"{lookup[key]['ml_id']} | {lookup[key]['titulo_ecom'][:60]}")
    st.warning("Las tasas de cuotas precargadas son las del script anterior, no una validación de tarifas por país. "
               "Confirma o reemplaza la tasa para cada mercado. Si mezclas países, se aplica la tasa ingresada a todos.")
    with st.form("roi_simulation_form_v2"):
        scenario = st.radio("Escenario", ["Cambio de precio", "ROI objetivo"], horizontal=True)
        price = st.number_input("Precio nuevo (moneda local de cada publicación)", min_value=0.0, value=0.0, step=100.0)
        objective = st.number_input("ROI mínimo objetivo (%)", min_value=0.0, max_value=500.0, value=30.0)
        campaign = st.selectbox("Referencia de cuotas", list(CAMPAIGN_CUOTAS))
        override = st.checkbox("Ingresar tasa de cuotas manual")
        manual_rate = st.number_input("Tasa manual de cuotas (%)", min_value=0.0, max_value=99.0, value=0.0)
        shipping = st.checkbox("Incluir costo de envío a cargo del vendedor", value=True)
        run = st.form_submit_button("Simular", use_container_width=True)
    if run:
        st.session_state.roi_results_v2 = []
        if not selected:
            st.warning("Selecciona al menos una publicación.")
        elif scenario == "Cambio de precio" and price <= 0:
            st.error("Ingresa un precio mayor a cero.")
        else:
            rate = manual_rate / 100 if override else CAMPAIGN_CUOTAS[campaign]
            results = []
            with st.spinner("Calculando con tarifas en memoria…"):
                for key in selected:
                    product = lookup[key]
                    try:
                        suggested = price if scenario == "Cambio de precio" else simular_escenario_2(
                            product, objective, rate, shipping, st.session_state.roi_tarifas_v2)
                        sim = calcular_rentabilidad(product, suggested, rate, shipping, st.session_state.roi_tarifas_v2)
                        results.append({"producto": product, "sim": sim,
                                        "campania": f"{campaign} · tasa aplicada {rate*100:.2f}%",
                                        "escenario": scenario, "objetivo": objective})
                    except Exception as exc:
                        results.append({"error": f"{product['ml_id']} ({product['country_code']}): {exc}"})
            st.session_state.roi_results_v2 = results
    if st.session_state.get("roi_results_v2"):
        st.subheader("Última simulación enviada")
        st.caption("Resultados de los parámetros y selección al pulsar Simular. Cambiar filtros no los recalcula.")
        export = []
        for item in st.session_state.roi_results_v2:
            if "error" in item:
                st.error(item["error"])
                continue
            product, sim = item["producto"], item["sim"]
            with st.expander(f"{product['country_code']} | {product['ml_id']} | {product['titulo_ecom']}", expanded=True):
                if item["escenario"] == "ROI objetivo":
                    st.write(f"Precio mínimo calculado para ROI ≥ {item['objetivo']:.2f}%: {fmt(sim['precio_venta_final_sim'])}")
                mostrar_comparativo(product, sim, item["campania"])
            export.append({"ml_id": product["ml_id"], "cuenta": product["cuenta"], **sim})
        if export:
            st.download_button("Descargar simulaciones CSV", pd.DataFrame(export).to_csv(index=False).encode("utf-8-sig"),
                               "simulaciones_roi.csv", "text/csv")


main()
