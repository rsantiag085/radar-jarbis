"""
Módulo de Telemetria e APM nativo (OpenTelemetry / ClickHouse) para o Radar Jarbis.

Envia de forma assíncrona e não-bloqueante:
- Traces e Spans (otel_traces)
- Logs estruturados correlacionados (otel_logs)
- Métricas contínuas (otel_metrics_gauge)
"""

import asyncio
import datetime
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("radardojarbis.telemetry")

CLICKHOUSE_URL = os.getenv("CLICKHOUSE_OTEL_URL", "http://34.121.123.56:8123")
ENABLED = os.getenv("OTEL_ENABLED", "true").lower() in ("true", "1", "yes")

_client: Optional[httpx.AsyncClient] = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=3.0)
    return _client


async def _insert_ch(table: str, data: Dict[str, Any]) -> None:
    if not ENABLED:
        return
    try:
        client = get_client()
        url = f"{CLICKHOUSE_URL}/?query=INSERT+INTO+otel.{table}+FORMAT+JSONEachRow"
        payload = json.dumps(data)
        resp = await client.post(url, content=payload, headers={"Content-Type": "application/json"})
        if resp.status_code != 200:
            logger.debug(f"Falha ao enviar telemetria ({table}): {resp.status_code} - {resp.text}")
    except Exception as e:
        logger.debug(f"Erro ao enviar telemetria para ClickHouse ({table}): {e}")


def fire_and_forget(coro):
    """Executa a corrotina em background sem bloquear o fluxo principal."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        pass


class TraceSpan:
    def __init__(
        self,
        service_name: str,
        span_name: str,
        span_kind: str = "SPAN_KIND_SERVER",
        trace_id: Optional[str] = None,
        parent_span_id: str = "",
        attributes: Optional[Dict[str, Any]] = None,
    ):
        self.service_name = service_name
        self.span_name = span_name
        self.span_kind = span_kind
        self.trace_id = trace_id or uuid.uuid4().hex
        self.span_id = uuid.uuid4().hex[:16]
        self.parent_span_id = parent_span_id
        self.attributes = {k: str(v) for k, v in (attributes or {}).items()}
        self.start_perf = time.perf_counter()
        self.status_code = "STATUS_CODE_OK"
        self.status_message = ""
        self.ended = False

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = str(value)

    def set_status(self, code: str, message: str = "") -> None:
        self.status_code = code
        self.status_message = message

    def log(self, message: str, severity: str = "INFO", extra_attributes: Optional[Dict[str, Any]] = None) -> None:
        """Registra um log correlacionado a este Trace e Span."""
        attrs = dict(self.attributes)
        if extra_attributes:
            attrs.update({k: str(v) for k, v in extra_attributes.items()})

        sev_map = {
            "DEBUG": 5,
            "INFO": 9,
            "WARN": 13,
            "WARNING": 13,
            "ERROR": 17,
            "FATAL": 21,
        }
        sev_num = sev_map.get(severity.upper(), 9)

        log_data = {
            "Timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f"),
            "TraceId": self.trace_id,
            "SpanId": self.span_id,
            "TraceFlags": 1,
            "SeverityText": severity.upper(),
            "SeverityNumber": sev_num,
            "ServiceName": self.service_name,
            "Body": message,
            "ResourceAttributes": {"service.name": self.service_name},
            "ScopeName": "radar.pipeline",
            "LogAttributes": {k: str(v) for k, v in attrs.items()},
        }
        fire_and_forget(_insert_ch("otel_logs", log_data))

    def end(self, status_code: Optional[str] = None, status_message: str = "") -> None:
        if self.ended:
            return
        self.ended = True

        if status_code:
            self.status_code = status_code
        if status_message:
            self.status_message = status_message

        duration_ns = int((time.perf_counter() - self.start_perf) * 1e9)
        dt_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")

        trace_data = {
            "Timestamp": dt_str,
            "TraceId": self.trace_id,
            "SpanId": self.span_id,
            "ParentSpanId": self.parent_span_id,
            "TraceState": "",
            "SpanName": self.span_name,
            "SpanKind": self.span_kind,
            "ServiceName": self.service_name,
            "ResourceSchemaUrl": "",
            "ResourceAttributes": {"service.name": self.service_name},
            "ScopeSchemaUrl": "",
            "ScopeName": "radar.pipeline",
            "ScopeVersion": "1.0",
            "ScopeAttributes": {},
            "SpanAttributes": {k: str(v) for k, v in self.attributes.items()},
            "Duration": duration_ns,
            "StatusCode": self.status_code,
            "StatusMessage": self.status_message,
        }
        fire_and_forget(_insert_ch("otel_traces", trace_data))

        # Emite métrica de latência da operação
        metric_data = {
            "ResourceAttributes": {"service.name": self.service_name},
            "ScopeName": "radar.pipeline",
            "ServiceName": self.service_name,
            "MetricName": "operation_latency_seconds",
            "MetricDescription": f"Latência da operação {self.span_name}",
            "MetricUnit": "s",
            "Attributes": {"operation": self.span_name, "status": self.status_code},
            "StartTimeUnix": dt_str,
            "TimeUnix": dt_str,
            "Value": round(duration_ns / 1e9, 4),
            "Flags": 0,
        }
        fire_and_forget(_insert_ch("otel_metrics_gauge", metric_data))


def start_span(
    service_name: str,
    span_name: str,
    span_kind: str = "SPAN_KIND_SERVER",
    attributes: Optional[Dict[str, Any]] = None,
) -> TraceSpan:
    return TraceSpan(
        service_name=service_name,
        span_name=span_name,
        span_kind=span_kind,
        attributes=attributes,
    )
