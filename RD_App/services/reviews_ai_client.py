from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable

import requests
import streamlit as st

from services.reviews_data import ReviewFilters, get_ai_context_metrics, iter_ai_review_batches

BATCH_ROWS = 80
MAX_BATCH_CHARS = 55_000
MAX_SINGLE_REVIEW_CHARS = 52_000
MAX_FINDINGS_CHARS = 50_000
MAX_FINDINGS_PER_CALL = 60
TIMEOUT = (10, 180)


class AIQueryError(RuntimeError):
    pass


def filter_signature(filters: ReviewFilters) -> str:
    data = asdict(filters)
    for key, value in data.items():
        if isinstance(value, (date, datetime)):
            data[key] = value.isoformat()
        elif isinstance(value, list):
            data[key] = sorted(map(str, value))
    return json.dumps(data, sort_keys=True, ensure_ascii=False)


def _api_config() -> tuple[str, str]:
    url = str(st.secrets.get("VERTEX_REVIEWS_API_URL", "")).strip().rstrip("/")
    token = str(st.secrets.get("VERTEX_REVIEWS_API_TOKEN", "")).strip()
    if not url.startswith("https://") or not token:
        raise AIQueryError("Configura VERTEX_REVIEWS_API_URL (HTTPS) y VERTEX_REVIEWS_API_TOKEN en Streamlit Secrets.")
    return url, token


def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    url, token = _api_config()
    try:
        response = requests.post(
            f"{url}{path}",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=TIMEOUT,
        )
        if response.status_code != 200:
            if response.status_code in (401, 403):
                raise AIQueryError("Cloud Run rechazó la autenticación. Revisa el token o los permisos del servicio.")
            if response.status_code == 413:
                raise AIQueryError("Cloud Run rechazó un bloque por tamaño. Reduce el tamaño del lote.")
            raise AIQueryError(f"Cloud Run respondió HTTP {response.status_code} en {path}. Consulta sus logs.")
        data = response.json()
        if not isinstance(data, dict):
            raise AIQueryError(f"Respuesta inválida de Cloud Run en {path}.")
        return data
    except AIQueryError:
        raise
    except (requests.RequestException, ValueError) as exc:
        raise AIQueryError(f"No se pudo completar {path}. Revisa la conexión y los logs de Cloud Run.") from exc


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Tipo no serializable: {type(value).__name__}")


def _json_size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, default=_json_default))


def _review_payload(row: dict[str, Any]) -> dict[str, Any]:
    result = {key: row.get(key) for key in (
        "row_id", "ml_id", "fecha_review", "estrellas", "titulo_review",
        "comentario", "titulo_ecom", "sku",
    )}
    if not result["row_id"]:
        raise AIQueryError("Se encontró una review sin row_id.")
    result["row_id"] = str(result["row_id"])
    if result["fecha_review"] is not None:
        result["fecha_review"] = result["fecha_review"].isoformat()
    if result["estrellas"] is not None:
        result["estrellas"] = int(result["estrellas"])
    for key in ("ml_id", "titulo_review", "comentario", "titulo_ecom", "sku"):
        if result[key] is not None:
            result[key] = str(result[key])
    if _json_size(result) > MAX_SINGLE_REVIEW_CHARS:
        raise AIQueryError(
            f"La review {result['row_id']} supera el tamaño permitido para análisis íntegro. "
            "No se ha recortado ni omitido."
        )
    return result


def _iter_payload_batches(filters: ReviewFilters):
    pending: list[dict[str, Any]] = []
    for rows in iter_ai_review_batches(filters, batch_size=BATCH_ROWS):
        for row in rows:
            review = _review_payload(row)
            candidate = pending + [review]
            if pending and (len(candidate) > BATCH_ROWS or _json_size(candidate) > MAX_BATCH_CHARS):
                yield pending
                pending = [review]
            else:
                pending = candidate
        if pending:
            yield pending
            pending = []


def _verified_findings(raw: Any, valid_ids: set[str]) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise AIQueryError("Cloud Run devolvió hallazgos en un formato inválido.")
    findings = []
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("finding"), str) or not isinstance(item.get("row_ids"), list):
            raise AIQueryError("Cloud Run devolvió un hallazgo inválido.")
        ids = list(dict.fromkeys(str(x) for x in item["row_ids"] if str(x) in valid_ids))[:20]
        if item["finding"].strip() and ids:
            findings.append({"finding": item["finding"].strip()[:1500], "row_ids": ids})
    return findings


def _groups(findings: list[dict[str, Any]]):
    group: list[dict[str, Any]] = []
    for finding in findings:
        if group and (len(group) >= MAX_FINDINGS_PER_CALL or _json_size(group + [finding]) > MAX_FINDINGS_CHARS):
            yield group
            group = []
        group.append(finding)
    if group:
        yield group


def _metrics_context(metrics: dict[str, Any], filters: ReviewFilters) -> str:
    values = {
        "filtros": json.loads(filter_signature(filters)),
        "metricas_sql": metrics,
        "nota": "Estrellas nulas quedan fuera del promedio; total_reviews incluye todas las filas filtradas.",
    }
    context = json.dumps(values, ensure_ascii=False, default=_json_default)
    if len(context) > 15_000:
        raise AIQueryError("Los filtros y las métricas exceden el límite de contexto de Cloud Run.")
    return context


def _direct_metric_answer(question: str, metrics: dict[str, Any]) -> str | None:
    q = re.sub(r"[^a-z0-9\s]", " ", question.casefold().translate(str.maketrans("áéíóúü", "aeiouu")))
    q = " ".join(q.split())
    if not re.search(r"\b(cuant[oa]s?|numero|cantidad|total|promedio|media|cuantas)\b", q):
        return None
    if re.search(r"\b(por que|porque|motivos?|razones?|causas?|comentarios?|dicen|mencionan|temas?|problemas?)\b", q):
        return None
    if re.search(r"\b(por|de|con)\s+(mes|semana|dia|fecha|anio|ano|periodo|cuenta|oferta|sku|producto|publicacion|ml id)\b", q):
        return None
    if re.search(r"\b(una|un|1|dos|2|tres|3|cuatro|4|cinco|5)\s+estrellas?\b", q):
        match = re.search(r"\b(una|un|1|dos|2|tres|3|cuatro|4|cinco|5)\s+estrellas?\b", q)
        number = {"una": 1, "un": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5}.get(match.group(1), match.group(1))
        return f"Hay {int(metrics[f'estrellas_{number}'] or 0):,} reviews de {number} estrella(s) con los filtros actuales."
    if re.search(r"\b(criticas?|negativas?|quejas?)\b", q):
        return f"Hay {int(metrics['quejas_criticas'] or 0):,} reviews críticas (1–2 estrellas) con los filtros actuales."
    if re.search(r"\b(positivas?|satisfech[oa]s?)\b", q):
        return f"Hay {int(metrics['positivas'] or 0):,} reviews positivas (4–5 estrellas) con los filtros actuales."
    if re.search(r"\b(promedio|media)\b", q) and re.search(r"\b(estrellas?|calificacion|rating)\b", q):
        value = metrics.get("promedio_estrellas")
        return f"El promedio de calificación es {value if value is not None else 'N/D'} de 5 estrellas para los filtros actuales."
    if re.search(r"\b(publicaciones?|ml ids?)\b", q):
        return f"Hay {int(metrics['publicaciones_unicas'] or 0):,} publicaciones únicas con los filtros actuales."
    if re.search(r"\b(skus?)\b", q):
        return f"Hay {int(metrics['skus_unicos'] or 0):,} SKU únicos asociados a las reviews filtradas."
    if re.search(r"\b(reviews?|resenas?|opiniones?)\b", q) and re.search(r"\b(cuant[oa]s?|numero|cantidad|total)\b", q):
        return f"Tenemos {int(metrics['total_reviews'] or 0):,} reviews en el universo filtrado actual."
    return None


def answer_reviews_question(
    question: str, filters: ReviewFilters, progress: Callable[[str], None]
) -> tuple[str, str]:
    if not question.strip() or len(question) > 2000:
        raise AIQueryError("Escribe una pregunta de entre 1 y 2000 caracteres.")
    progress("Consultando métricas exactas en Neon…")
    metrics = get_ai_context_metrics(filters)
    total = int(metrics["total_reviews"] or 0)
    expected = int(metrics["reviews_con_texto"] or 0)
    if total == 0:
        return "No se encontraron reviews con los filtros activos.", "0 reviews filtradas."
    direct_answer = _direct_metric_answer(question, metrics)
    if direct_answer is not None:
        return direct_answer, f"Fuente: COUNT/AVG de SQL sobre {total:,} reviews filtradas. No se llamó a Vertex AI."

    _api_config()
    metrics_text = _metrics_context(metrics, filters)
    findings: list[dict[str, Any]] = []
    analyzed = 0
    batches = 0
    valid_ids: set[str] = set()
    progress(f"Buscando evidencia: {expected:,} reviews con texto en {total:,} filas filtradas…")
    try:
        for batch in _iter_payload_batches(filters):
            batches += 1
            progress(f"Analizando lote {batches} · {analyzed:,} de {expected:,} reviews con texto procesadas…")
            result = _post("/analyze-batch", {"question": question, "reviews": batch})
            if result.get("reviews_received") != len(batch):
                raise AIQueryError(f"Cobertura inconsistente en lote {batches}.")
            current_ids = {item["row_id"] for item in batch}
            if valid_ids.intersection(current_ids):
                raise AIQueryError("Se detectó row_id repetido entre lotes.")
            valid_ids.update(current_ids)
            findings.extend(_verified_findings(result.get("findings"), current_ids))
            analyzed += len(batch)
    except Exception as exc:
        if isinstance(exc, AIQueryError):
            raise AIQueryError(f"Análisis incompleto: {analyzed:,} reviews confirmadas; lote {batches} sin completar. {exc}") from exc
        raise AIQueryError(f"Análisis incompleto tras {analyzed:,} reviews confirmadas. Revisa Neon y Cloud Run.") from exc

    if analyzed != expected:
        raise AIQueryError(
            f"La base cambió durante la consulta o hubo una discrepancia: "
            f"{analyzed:,} reviews leídas frente a {expected:,} contadas. "
            "No se publicará una respuesta como completa; vuelve a preguntar."
        )

    if len(findings) > MAX_FINDINGS_PER_CALL or _json_size(findings) > MAX_FINDINGS_CHARS:
        progress("Organizando hallazgos de todos los lotes…")
        previous_count = len(findings)
        for _ in range(8):
            reduced: list[dict[str, Any]] = []
            for group in _groups(findings):
                result = _post("/synthesize", {
                    "question": question, "metrics_context": metrics_text,
                    "findings": group, "analyzed_reviews": analyzed,
                    "expected_reviews": expected, "complete": True, "phase": "reduce",
                })
                reduced.extend(_verified_findings(result.get("findings"), valid_ids))
            findings = reduced
            if len(findings) <= MAX_FINDINGS_PER_CALL and _json_size(findings) <= MAX_FINDINGS_CHARS:
                break
            if not findings or len(findings) >= previous_count:
                raise AIQueryError("Hay demasiados hallazgos para una síntesis íntegra; ajusta los filtros y repite la pregunta.")
            previous_count = len(findings)
        else:
            raise AIQueryError("No se pudo condensar toda la evidencia sin exceder el límite del servicio.")

    progress("Pensando y preparando respuesta con la evidencia verificada…")
    response = _post("/synthesize", {
        "question": question, "metrics_context": metrics_text,
        "findings": findings, "analyzed_reviews": analyzed,
        "expected_reviews": expected, "complete": True, "phase": "final",
    })
    if response.get("complete") is not True or response.get("analyzed_reviews") != analyzed or response.get("expected_reviews") != expected:
        raise AIQueryError("Cloud Run devolvió una cobertura diferente; no se mostrará como completa.")
    answer = response.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise AIQueryError("Cloud Run no devolvió una respuesta final válida.")
    coverage = f"Cobertura: {analyzed:,} de {expected:,} reviews con texto procesadas; {total:,} reviews filtradas en total."
    return answer.strip(), coverage
