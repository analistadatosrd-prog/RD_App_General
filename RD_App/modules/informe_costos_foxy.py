import json
import time
from io import BytesIO

import pandas as pd
import requests
import streamlit as st
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

GRAPHQL_URL = "https://api.ecomexperts.com/graphql"

# Ajustar solo esta URL si el login real de EcomExperts usa otra ruta.
# No es una mutación GraphQL: debe ser el endpoint HTTP que crea la cookie/sesión.
ECOM_LOGIN_URL = "https://app.ecomexperts.com/login"

TIMEOUT = (20, 90)
PAGE_DELAY = 0.05

ACCOUNT_ID_CUENTAS = {
    "33833": "rd_argentina",
    "33526": "insuoffice",
    "34398": "tucocina_tufarmacia",
    "33920": "lalu_modernpinup",
    "33869": "rd_chile",
    "34372": "rd_mexico",
}

CUENTAS_SESION_PRINCIPAL = {
    "rd_argentina",
    "insuoffice",
    "tucocina_tufarmacia",
    "lalu_modernpinup",
}

CREDENCIALES_ADICIONALES = {
    "rd_chile": {
        "email_address": "analista.datoschile@outlook.com",
        "password": "Data.2025**",
    },
    "rd_mexico": {
        "email_address": "analista.datosmxn@outlook.com",
        "password": "Data.2025**",
    },
}

COMMON_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate",
}

st.set_page_config(
    page_title="Informe de Costos Foxy",
    page_icon="📦",
    layout="wide",
)


def configure_session(session):
    if session is None:
        raise ValueError("La sesión de EcomExperts no está disponible.")

    session.headers.update(COMMON_HEADERS)

    retry = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["POST"]),
        raise_on_status=False,
    )

    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=20,
        pool_maxsize=20,
    )

    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


def ensure_session_ready(session):
    return configure_session(session)


def post_graphql(session, query):
    payload = {
        "query": query,
        "operationName": None,
    }

    resp = session.post(
        GRAPHQL_URL,
        data=json.dumps(payload),
        timeout=TIMEOUT,
    )
    resp.raise_for_status()

    data = resp.json()

    if data.get("errors"):
        raise ValueError(f"GraphQL error: {data['errors']}")

    return data


def extract_token_from_response(response):
    """
    Intenta identificar un token si el endpoint REST lo devuelve
    en JSON, headers o cookies. Si el login autentica solo con cookie,
    devuelve None y la sesión seguirá siendo válida mediante cookies.
    """
    possible_header_keys = [
        "Authorization",
        "authorization",
        "X-Auth-Token",
        "x-auth-token",
        "X-Access-Token",
        "x-access-token",
        "Token",
        "token",
    ]

    for header_name in possible_header_keys:
        token = response.headers.get(header_name)
        if token:
            return token

    try:
        data = response.json()
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    possible_token_paths = [
        ("token",),
        ("access_token",),
        ("accessToken",),
        ("jwt",),
        ("data", "token"),
        ("data", "access_token"),
        ("data", "accessToken"),
        ("user", "token"),
        ("User", "token"),
    ]

    for path in possible_token_paths:
        current = data

        try:
            for key in path:
                current = current[key]

            if current:
                return str(current)
        except Exception:
            continue

    return None


def session_has_auth_cookie(session):
    """
    Revisa si el login dejó alguna cookie de sesión/autorización.
    """
    if session is None:
        return False

    cookie_names = {
        str(cookie.name).lower()
        for cookie in session.cookies
    }

    keywords = [
        "session",
        "auth",
        "token",
        "jwt",
        "remember",
        "user",
    ]

    return any(
        any(keyword in cookie_name for keyword in keywords)
        for cookie_name in cookie_names
    )


def login_ecomexperts_rest(email_address, password):
    """
    Crea una requests.Session independiente y ejecuta el login REST.

    Payload enviado:
    {
        "User": {
            "email_address": "...",
            "password": "..."
        }
    }

    Se soportan tres escenarios:
    1. Login basado en cookie.
    2. Login basado en token devuelto en JSON.
    3. Login basado en header Authorization / X-Auth-Token.
    """
    session = configure_session(requests.Session())

    payload = {
        "User": {
            "email_address": email_address,
            "password": password,
        }
    }

    response = session.post(
        ECOM_LOGIN_URL,
        json=payload,
        timeout=TIMEOUT,
        allow_redirects=True,
    )

    response.raise_for_status()

    token = extract_token_from_response(response)

    if token:
        if token.lower().startswith("bearer "):
            session.headers["Authorization"] = token
        else:
            session.headers["Authorization"] = f"Bearer {token}"

    if not token and not session_has_auth_cookie(session):
        try:
            response_data = response.json()
        except Exception:
            response_data = response.text[:500]

        raise ValueError(
            "El login respondió correctamente, pero no se detectó "
            "token ni cookie de sesión. "
            f"URL utilizada: {ECOM_LOGIN_URL}. "
            f"Respuesta: {response_data}"
        )

    return session


def fetch_ml_listings_fast(session, status_callback=None, account_filter=None):
    all_rows = []
    current_page = 1

    while True:
        if status_callback:
            status_callback(f"Consultando mlListings - página {current_page}...")

        query = f"""
        query {{
          mlListings {{
            find(page: {current_page}, filters:[{{ filter:"active", values:["1"] }}]) {{
              data {{
                id
                accountId
                owner
                ownerId
                productListings {{
                  qty
                  productId
                  productVariantId
                  product {{
                    sku
                    title
                  }}
                }}
              }}
            }}
          }}
        }}
        """

        data = post_graphql(session, query)

        listings = (
            data.get("data", {})
            .get("mlListings", {})
            .get("find", {})
            .get("data", [])
        )

        if not listings:
            break

        for listing in listings:
            account_id = str(listing.get("accountId", "") or "")

            if account_id not in ACCOUNT_ID_CUENTAS:
                continue

            cuenta = ACCOUNT_ID_CUENTAS.get(account_id, "sin_clasificar")

            if account_filter and cuenta != account_filter:
                continue

            owner = str(listing.get("owner", "") or "")
            mla = str(listing.get("ownerId", "") or "")

            for item in listing.get("productListings") or []:
                product = item.get("product") or {}

                all_rows.append(
                    {
                        "cuenta": cuenta,
                        "mla": mla,
                        "owner": owner,
                        "account_id": account_id,
                        "product_id": str(item.get("productId", "") or ""),
                        "product_variant_id": str(
                            item.get("productVariantId", "") or ""
                        ),
                        "sku": str(product.get("sku", "") or "").strip(),
                        "titulo_producto_base": str(
                            product.get("title", "") or ""
                        ).strip(),
                        "unidades": pd.to_numeric(
                            item.get("qty"),
                            errors="coerce",
                        ),
                    }
                )

        current_page += 1

        if PAGE_DELAY:
            time.sleep(PAGE_DELAY)

    df = pd.DataFrame(all_rows)

    if df.empty:
        return pd.DataFrame(
            columns=[
                "cuenta",
                "mla",
                "owner",
                "account_id",
                "product_id",
                "product_variant_id",
                "sku",
                "titulo_producto_base",
                "unidades",
            ]
        )

    df["sku"] = df["sku"].astype(str).str.strip()
    df["mla"] = df["mla"].astype(str).str.strip()
    df["cuenta"] = df["cuenta"].astype(str).str.strip()
    df["unidades"] = pd.to_numeric(df["unidades"], errors="coerce")

    return df


def fetch_products_fast(session, status_callback=None):
    rows = []
    current_page = 1

    while True:
        if status_callback:
            status_callback(f"Consultando products - página {current_page}...")

        query = f"""
        query {{
          products {{
            find(page: {current_page}) {{
              data {{
                sku
                title
                tax
                variants {{
                  sku
                  cost
                }}
              }}
            }}
          }}
        }}
        """

        data = post_graphql(session, query)

        products = (
            data.get("data", {})
            .get("products", {})
            .get("find", {})
            .get("data", [])
        )

        if not products:
            break

        for product in products:
            product_sku = str(product.get("sku", "") or "").strip()
            product_title = str(product.get("title", "") or "").strip()
            product_tax = product.get("tax", None)

            tax_value = None

            if isinstance(product_tax, dict):
                for key in [
                    "iva",
                    "IVA",
                    "tax",
                    "value",
                    "amount",
                    "percentage",
                    "percent",
                ]:
                    if key in product_tax:
                        tax_value = product_tax[key]
                        break
            else:
                tax_value = product_tax

            variants = product.get("variants") or []

            if variants:
                costs = [
                    pd.to_numeric(variant.get("cost"), errors="coerce")
                    for variant in variants
                ]
                costs = [cost for cost in costs if pd.notna(cost)]
                max_cost = max(costs) if costs else None
            else:
                max_cost = None

            rows.append(
                {
                    "sku": product_sku,
                    "titulo_catalogo": product_title,
                    "costo_unitario": pd.to_numeric(
                        max_cost,
                        errors="coerce",
                    ),
                    "iva": pd.to_numeric(
                        tax_value,
                        errors="coerce",
                    ),
                }
            )

        current_page += 1

        if PAGE_DELAY:
            time.sleep(PAGE_DELAY)

    df = pd.DataFrame(rows)

    if df.empty:
        return pd.DataFrame(
            columns=[
                "sku",
                "titulo_catalogo",
                "costo_unitario",
                "iva",
            ]
        )

    df["sku"] = df["sku"].astype(str).str.strip()

    return (
        df.groupby("sku", as_index=False)
        .agg(
            {
                "titulo_catalogo": "first",
                "costo_unitario": "max",
                "iva": "max",
            }
        )
    )


def clasificar_mla(num_skus, total_qty):
    if num_skus == 1 and total_qty == 1:
        return "monoproducto"

    if num_skus == 1 and total_qty > 1:
        return "monoproducto multioferta"

    if num_skus > 1:
        return "combo"

    return "sin clasificar"


def build_outputs(df_listings, df_products, status_callback=None):
    if df_listings.empty:
        detalle = pd.DataFrame(
            columns=[
                "cuenta",
                "mla",
                "sku",
                "unidades",
                "costo_unitario",
                "costo_total_sku",
                "iva",
                "titulo_final",
            ]
        )

        final_df = pd.DataFrame(
            columns=[
                "cuenta",
                "mla",
                "titulo_producto",
                "skus_asociados",
                "unidades_totales",
                "costo_total_mla",
                "iva",
                "cant_sku",
                "tipo_producto",
            ]
        )

        return detalle, final_df

    if status_callback:
        status_callback(
            "Depurando SKUs duplicados por cuenta + MLA + SKU (qty máximo)..."
        )

    detalle = (
        df_listings.groupby(
            ["cuenta", "mla", "sku"],
            as_index=False,
        )
        .agg(
            {
                "unidades": "max",
                "titulo_producto_base": lambda s: " | ".join(
                    sorted(
                        set(
                            [
                                str(value).strip()
                                for value in s
                                if str(value).strip()
                            ]
                        )
                    )
                ),
                "owner": "first",
                "account_id": "first",
            }
        )
    )

    if status_callback:
        status_callback("Cruzando SKUs únicos contra catálogo de costos...")

    detalle = detalle.merge(
        df_products,
        on="sku",
        how="left",
    )

    detalle["costo_unitario"] = pd.to_numeric(
        detalle["costo_unitario"],
        errors="coerce",
    ).fillna(0)

    detalle["iva"] = pd.to_numeric(
        detalle["iva"],
        errors="coerce",
    )

    detalle["unidades"] = pd.to_numeric(
        detalle["unidades"],
        errors="coerce",
    ).fillna(0)

    detalle["titulo_final"] = (
        detalle["titulo_producto_base"]
        .replace("", pd.NA)
        .fillna(detalle["titulo_catalogo"])
    )

    detalle["costo_total_sku"] = (
        detalle["costo_unitario"]
        * detalle["unidades"]
    )

    detalle = (
        detalle[
            [
                "cuenta",
                "mla",
                "sku",
                "unidades",
                "costo_unitario",
                "costo_total_sku",
                "iva",
                "titulo_final",
            ]
        ]
        .sort_values(["cuenta", "mla", "sku"])
        .reset_index(drop=True)
    )

    if status_callback:
        status_callback("Construyendo resumen final por cuenta + MLA...")

    final_df = (
        detalle.groupby(
            ["cuenta", "mla"],
            as_index=False,
        )
        .agg(
            titulo_producto=(
                "titulo_final",
                lambda s: " | ".join(
                    sorted(
                        set(
                            [
                                str(value).strip()
                                for value in s
                                if str(value).strip()
                            ]
                        )
                    )
                ),
            ),
            skus_asociados=(
                "sku",
                lambda s: " | ".join(
                    sorted(
                        set(
                            [
                                str(value).strip()
                                for value in s
                                if str(value).strip()
                            ]
                        )
                    )
                ),
            ),
            unidades_totales=("unidades", "sum"),
            costo_total_mla=("costo_total_sku", "sum"),
            iva=("iva", "max"),
            cant_sku=("sku", "nunique"),
        )
    )

    final_df["tipo_producto"] = final_df.apply(
        lambda row: clasificar_mla(
            row["cant_sku"],
            row["unidades_totales"],
        ),
        axis=1,
    )

    final_df = (
        final_df[
            [
                "cuenta",
                "mla",
                "titulo_producto",
                "skus_asociados",
                "unidades_totales",
                "costo_total_mla",
                "iva",
                "cant_sku",
                "tipo_producto",
            ]
        ]
        .sort_values(["cuenta", "tipo_producto", "mla"])
        .reset_index(drop=True)
    )

    return detalle, final_df


def init_state():
    defaults = {
        "foxy_df_final": pd.DataFrame(),
        "foxy_df_detalle": pd.DataFrame(),
        "foxy_df_vista": pd.DataFrame(),
        "foxy_df_detalle_vista": pd.DataFrame(),
        "foxy_status": "Listo para consultar",
        "foxy_detalle_carga": "Sin consultas ejecutadas",
        "foxy_buscar_titulo": "",
        "foxy_buscar_sku": "",
        "foxy_buscar_mla": "",
        "foxy_tipo": "Todos",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def apply_filters():
    if st.session_state.foxy_df_final.empty:
        st.session_state.foxy_df_vista = (
            st.session_state.foxy_df_final.copy()
        )
        st.session_state.foxy_df_detalle_vista = (
            st.session_state.foxy_df_detalle.copy()
        )
        return

    vista = st.session_state.foxy_df_final.copy()

    filtro_titulo = st.session_state.foxy_buscar_titulo.strip()
    filtro_sku = st.session_state.foxy_buscar_sku.strip()
    filtro_mla = st.session_state.foxy_buscar_mla.strip()
    tipo = st.session_state.foxy_tipo.strip()

    if filtro_titulo:
        vista = vista[
            vista["titulo_producto"]
            .astype(str)
            .str.contains(filtro_titulo, case=False, na=False)
        ]

    if filtro_sku:
        vista = vista[
            vista["skus_asociados"]
            .astype(str)
            .str.contains(filtro_sku, case=False, na=False)
        ]

    if filtro_mla:
        vista = vista[
            vista["mla"]
            .astype(str)
            .str.contains(filtro_mla, case=False, na=False)
        ]

    if tipo and tipo != "Todos":
        vista = vista[
            vista["tipo_producto"] == tipo
        ]

    st.session_state.foxy_df_vista = vista.copy()

    detalle_vista = st.session_state.foxy_df_detalle.copy()

    if filtro_mla:
        detalle_vista = detalle_vista[
            detalle_vista["mla"]
            .astype(str)
            .str.contains(filtro_mla, case=False, na=False)
        ]

    if filtro_sku:
        detalle_vista = detalle_vista[
            detalle_vista["sku"]
            .astype(str)
            .str.contains(filtro_sku, case=False, na=False)
        ]

    if filtro_titulo:
        detalle_vista = detalle_vista[
            detalle_vista["titulo_final"]
            .astype(str)
            .str.contains(filtro_titulo, case=False, na=False)
        ]

    if tipo and tipo != "Todos":
        mlas_validos = set(vista["mla"].astype(str).tolist())

        detalle_vista = detalle_vista[
            detalle_vista["mla"]
            .astype(str)
            .isin(mlas_validos)
        ]

    st.session_state.foxy_df_detalle_vista = detalle_vista.copy()


def excel_bytes(df_vista, df_detalle_vista):
    try:
        import xlsxwriter  # noqa: F401
        engine = "xlsxwriter"
    except Exception:
        try:
            import openpyxl  # noqa: F401
            engine = "openpyxl"
        except Exception:
            return None

    output = BytesIO()

    with pd.ExcelWriter(output, engine=engine) as writer:
        df_vista.to_excel(
            writer,
            index=False,
            sheet_name="tabla_final",
        )

        df_detalle_vista.to_excel(
            writer,
            index=False,
            sheet_name="detalle_mla_sku",
        )

    return output.getvalue()


def update_status(message: str):
    st.session_state.foxy_detalle_carga = message


def consultar_datos_con_multiples_sesiones(status_callback=None):
    """
    Consulta unificada:

    - Sesión dejada por el login de la app:
      rd_argentina, insuoffice, tucocina_tufarmacia, lalu_modernpinup.

    - Sesiones internas REST:
      rd_chile y rd_mexico.

    Cada sesión consulta su propio catálogo de productos, para que el
    costo del SKU corresponda a la cuenta donde fue encontrado.
    """
    session_principal = st.session_state.get("ecom_session")

    if session_principal is None:
        raise ValueError(
            "La sesión principal de EcomExperts no está disponible."
        )

    session_principal = ensure_session_ready(session_principal)

    errores = []
    bloques_listings = []
    bloques_productos = []

    if status_callback:
        status_callback(
            "Consultando listados de cuentas de la sesión principal..."
        )

    try:
        listings_principal = fetch_ml_listings_fast(
            session_principal,
            status_callback=status_callback,
        )

        listings_principal = listings_principal[
            listings_principal["cuenta"].isin(
                CUENTAS_SESION_PRINCIPAL
            )
        ].reset_index(drop=True)

        bloques_listings.append(listings_principal)

        if status_callback:
            status_callback(
                "Consultando catálogo de costos de la sesión principal..."
            )

        productos_principal = fetch_products_fast(
            session_principal,
            status_callback=None,
        )

        productos_principal["cuenta"] = "__sesion_principal__"
        bloques_productos.append(productos_principal)

    except Exception as exc:
        raise ValueError(
            f"No fue posible consultar las cuentas de la sesión principal: {exc}"
        ) from exc

    for cuenta, credenciales in CREDENCIALES_ADICIONALES.items():
        try:
            if status_callback:
                status_callback(f"Autenticando internamente {cuenta}...")

            session_adicional = login_ecomexperts_rest(
                email_address=credenciales["email_address"],
                password=credenciales["password"],
            )

            if status_callback:
                status_callback(f"Consultando listados de {cuenta}...")

            listings_cuenta = fetch_ml_listings_fast(
                session_adicional,
                status_callback=None,
                account_filter=cuenta,
            )

            if not listings_cuenta.empty:
                bloques_listings.append(listings_cuenta)

                if status_callback:
                    status_callback(
                        f"Consultando catálogo de costos de {cuenta}..."
                    )

                productos_cuenta = fetch_products_fast(
                    session_adicional,
                    status_callback=None,
                )

                productos_cuenta["cuenta"] = cuenta
                bloques_productos.append(productos_cuenta)

            else:
                errores.append(
                    f"{cuenta}: autenticación correcta, pero no se hallaron "
                    "listados activos para el account_id configurado."
                )

        except Exception as exc:
            errores.append(
                f"Error al consultar {cuenta}: {exc}"
            )

    if bloques_listings:
        df_listings = pd.concat(
            bloques_listings,
            ignore_index=True,
        )
    else:
        df_listings = pd.DataFrame(
            columns=[
                "cuenta",
                "mla",
                "owner",
                "account_id",
                "product_id",
                "product_variant_id",
                "sku",
                "titulo_producto_base",
                "unidades",
            ]
        )

    if df_listings.empty:
        detalle_vacio, final_vacio = build_outputs(
            df_listings,
            pd.DataFrame(
                columns=[
                    "sku",
                    "titulo_catalogo",
                    "costo_unitario",
                    "iva",
                ]
            ),
        )
        return detalle_vacio, final_vacio, errores

    # Se asigna la llave de catálogo correspondiente a cada cuenta.
    df_listings["catalogo_cuenta"] = df_listings["cuenta"].where(
        df_listings["cuenta"].isin(CREDENCIALES_ADICIONALES.keys()),
        "__sesion_principal__",
    )

    if bloques_productos:
        df_productos = pd.concat(
            bloques_productos,
            ignore_index=True,
        )
    else:
        df_productos = pd.DataFrame(
            columns=[
                "sku",
                "titulo_catalogo",
                "costo_unitario",
                "iva",
                "cuenta",
            ]
        )

    if not df_productos.empty:
        df_productos["sku"] = (
            df_productos["sku"]
            .astype(str)
            .str.strip()
        )

        df_productos = (
            df_productos.groupby(
                ["cuenta", "sku"],
                as_index=False,
            )
            .agg(
                {
                    "titulo_catalogo": "first",
                    "costo_unitario": "max",
                    "iva": "max",
                }
            )
            .rename(columns={"cuenta": "catalogo_cuenta"})
        )

    detalle_bruto = (
        df_listings.groupby(
            [
                "cuenta",
                "mla",
                "sku",
                "catalogo_cuenta",
            ],
            as_index=False,
        )
        .agg(
            {
                "unidades": "max",
                "titulo_producto_base": lambda serie: " | ".join(
                    sorted(
                        set(
                            [
                                str(valor).strip()
                                for valor in serie
                                if str(valor).strip()
                            ]
                        )
                    )
                ),
            }
        )
    )

    detalle_bruto = detalle_bruto.merge(
        df_productos,
        on=["catalogo_cuenta", "sku"],
        how="left",
    )

    detalle_bruto["costo_unitario"] = pd.to_numeric(
        detalle_bruto["costo_unitario"],
        errors="coerce",
    ).fillna(0)

    detalle_bruto["iva"] = pd.to_numeric(
        detalle_bruto["iva"],
        errors="coerce",
    )

    detalle_bruto["unidades"] = pd.to_numeric(
        detalle_bruto["unidades"],
        errors="coerce",
    ).fillna(0)

    detalle_bruto["titulo_final"] = (
        detalle_bruto["titulo_producto_base"]
        .replace("", pd.NA)
        .fillna(detalle_bruto["titulo_catalogo"])
    )

    detalle_bruto["costo_total_sku"] = (
        detalle_bruto["costo_unitario"]
        * detalle_bruto["unidades"]
    )

    detalle_df = (
        detalle_bruto[
            [
                "cuenta",
                "mla",
                "sku",
                "unidades",
                "costo_unitario",
                "costo_total_sku",
                "iva",
                "titulo_final",
            ]
        ]
        .sort_values(["cuenta", "mla", "sku"])
        .reset_index(drop=True)
    )

    final_df = (
        detalle_df.groupby(
            ["cuenta", "mla"],
            as_index=False,
        )
        .agg(
            titulo_producto=(
                "titulo_final",
                lambda serie: " | ".join(
                    sorted(
                        set(
                            [
                                str(valor).strip()
                                for valor in serie
                                if str(valor).strip()
                            ]
                        )
                    )
                ),
            ),
            skus_asociados=(
                "sku",
                lambda serie: " | ".join(
                    sorted(
                        set(
                            [
                                str(valor).strip()
                                for valor in serie
                                if str(valor).strip()
                            ]
                        )
                    )
                ),
            ),
            unidades_totales=("unidades", "sum"),
            costo_total_mla=("costo_total_sku", "sum"),
            iva=("iva", "max"),
            cant_sku=("sku", "nunique"),
        )
    )

    final_df["tipo_producto"] = final_df.apply(
        lambda row: clasificar_mla(
            row["cant_sku"],
            row["unidades_totales"],
        ),
        axis=1,
    )

    final_df = (
        final_df[
            [
                "cuenta",
                "mla",
                "titulo_producto",
                "skus_asociados",
                "unidades_totales",
                "costo_total_mla",
                "iva",
                "cant_sku",
                "tipo_producto",
            ]
        ]
        .sort_values(["cuenta", "tipo_producto", "mla"])
        .reset_index(drop=True)
    )

    return detalle_df, final_df, errores


init_state()

st.title("Informe de Costos Foxy")
st.caption(
    "Consulta costos por MLA y detalle SKU desde EcomExperts "
    "(incluye rd_chile y rd_mexico)."
)

if not st.session_state.get("authenticated"):
    st.error("No hay una sesión autenticada.")
    st.stop()

session_principal = st.session_state.get("ecom_session")

if session_principal is None:
    st.error("La sesión principal de EcomExperts no está disponible.")
    st.stop()

col1, col2 = st.columns([1, 3])

with col1:
    consultar = st.button(
        "Consultar datos",
        type="primary",
        use_container_width=True,
    )

    if consultar:
        try:
            with st.spinner(
                "Consultando información fresca de todas las cuentas..."
            ):
                inicio = time.time()

                detalle_df, final_df, errores = (
                    consultar_datos_con_multiples_sesiones(
                        status_callback=update_status
                    )
                )

                st.session_state.foxy_df_detalle = detalle_df.copy()
                st.session_state.foxy_df_final = final_df.copy()
                st.session_state.foxy_status = (
                    f"Consulta completada en {round(time.time() - inicio, 2)} s"
                )
                st.session_state.foxy_detalle_carga = (
                    "Carga finalizada correctamente."
                )
                st.session_state.foxy_buscar_titulo = ""
                st.session_state.foxy_buscar_sku = ""
                st.session_state.foxy_buscar_mla = ""
                st.session_state.foxy_tipo = "Todos"

                apply_filters()

            st.success(st.session_state.foxy_status)

            if errores:
                st.warning(
                    "La consulta terminó, pero hubo observaciones "
                    "en una o más cuentas:"
                )

                for error in errores:
                    st.caption(error)

        except Exception as exc:
            st.session_state.foxy_status = "Error en consulta"
            st.session_state.foxy_detalle_carga = (
                "La carga se interrumpió por un error."
            )
            st.error(f"Error: {exc}")

with col2:
    st.write(
        f"**Estado de carga:** "
        f"{st.session_state.foxy_detalle_carga}"
    )
    st.write(
        f"**Estado general:** "
        f"{st.session_state.foxy_status}"
    )

st.subheader("Filtros")

filter_cols = st.columns([2, 2, 2, 2, 1])

with filter_cols[0]:
    st.text_input(
        "Título",
        key="foxy_buscar_titulo",
        on_change=apply_filters,
    )

with filter_cols[1]:
    st.text_input(
        "SKU",
        key="foxy_buscar_sku",
        on_change=apply_filters,
    )

with filter_cols[2]:
    st.text_input(
        "MLA",
        key="foxy_buscar_mla",
        on_change=apply_filters,
    )

with filter_cols[3]:
    tipos = ["Todos"]

    if not st.session_state.foxy_df_final.empty:
        tipos += sorted(
            st.session_state.foxy_df_final["tipo_producto"]
            .dropna()
            .unique()
            .tolist()
        )

    st.selectbox(
        "Tipo",
        options=tipos,
        key="foxy_tipo",
        on_change=apply_filters,
    )

with filter_cols[4]:
    if st.button("Limpiar", use_container_width=True):
        st.session_state.foxy_buscar_titulo = ""
        st.session_state.foxy_buscar_sku = ""
        st.session_state.foxy_buscar_mla = ""
        st.session_state.foxy_tipo = "Todos"

        apply_filters()
        st.rerun()

apply_filters()

m1, m2, m3 = st.columns(3)

with m1:
    st.metric(
        "MLA filtrados",
        len(st.session_state.foxy_df_vista),
    )

with m2:
    st.metric(
        "Costo total filtrado",
        round(
            st.session_state.foxy_df_vista[
                "costo_total_mla"
            ].sum(),
            2,
        )
        if not st.session_state.foxy_df_vista.empty
        else 0,
    )

with m3:
    st.metric(
        "Unidades totales filtradas",
        round(
            st.session_state.foxy_df_vista[
                "unidades_totales"
            ].sum(),
            2,
        )
        if not st.session_state.foxy_df_vista.empty
        else 0,
    )

st.subheader("Tabla final por MLA")

st.dataframe(
    st.session_state.foxy_df_vista,
    use_container_width=True,
    hide_index=True,
)

st.subheader("Detalle MLA + SKU")

st.dataframe(
    st.session_state.foxy_df_detalle_vista,
    use_container_width=True,
    hide_index=True,
)

if not st.session_state.foxy_df_vista.empty:
    c1, c2 = st.columns(2)

    with c1:
        st.download_button(
            "Descargar CSV",
            data=(
                st.session_state.foxy_df_vista
                .to_csv(index=False)
                .encode("utf-8-sig")
            ),
            file_name="informe_costos_foxy_filtrado.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with c2:
        excel_data = excel_bytes(
            st.session_state.foxy_df_vista,
            st.session_state.foxy_df_detalle_vista,
        )

        if excel_data is not None:
            st.download_button(
                "Descargar Excel",
                data=excel_data,
                file_name="informe_costos_foxy_filtrado.xlsx",
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
                    "Excel no disponible: falta instalar openpyxl "
                    "o xlsxwriter en el entorno."
                ),
            )
