"""
Módulo de servidor de métricas com suporte duplo:
- /metrics      : Formato de texto padrão do Prometheus (Prometheus exposition format)
- /metrics.json : Payload JSON leve para consumo direto pelo Zabbix via JSONPath
"""

import json
import logging
import resource
import threading
from typing import Any, Callable, Dict, Optional

import prometheus_client
from prometheus_client import REGISTRY
from prometheus_client.exposition import (
    ThreadingWSGIServer,
    _get_best_family,
    _SilentHandler,
    make_wsgi_app,
)
from wsgiref.simple_server import make_server

logger = logging.getLogger("radardojarbis.metrics")


def get_process_memory_rss_bytes() -> int:
    """Retorna a memória RSS residente atual do processo em bytes."""
    try:
        # ru_maxrss no Linux retorna em Kilobytes
        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
    except Exception:
        return 0


def extract_counter_value(metric: Any) -> float:
    """Extrai o valor numérico de um Counter ou Gauge do prometheus_client."""
    try:
        if hasattr(metric, "_value"):
            return float(metric._value.get())
        if hasattr(metric, "_metrics"):
            # Métricas com labels (ex: reason="duplicate")
            return float(sum(m._value.get() for m in metric._metrics.values()))
    except Exception:
        pass
    return 0.0


def start_metrics_server(
    port: int,
    json_provider: Optional[Callable[[], Dict[str, Any]]] = None,
    addr: str = "0.0.0.0",
) -> Any:
    """
    Inicia o servidor WSGI em thread daemon atendendo:
    - GET /metrics      -> Prometheus text exposition
    - GET /metrics.json -> JSON payload
    """
    prom_app = make_wsgi_app(REGISTRY)

    def wsgi_app(environ: Dict[str, Any], start_response: Callable[..., Any]) -> Any:
        path = environ.get("PATH_INFO", "")
        if path in ("/metrics.json", "/json"):
            try:
                data = json_provider() if json_provider else {}
                payload = json.dumps(data, indent=2).encode("utf-8")
                start_response(
                    "200 OK",
                    [
                        ("Content-Type", "application/json; charset=utf-8"),
                        ("Content-Length", str(len(payload))),
                    ],
                )
                return [payload]
            except Exception as e:
                logger.error(f"Erro ao gerar payload de métricas JSON: {e}")
                err_payload = json.dumps({"error": str(e)}).encode("utf-8")
                start_response(
                    "500 Internal Server Error",
                    [
                        ("Content-Type", "application/json"),
                        ("Content-Length", str(len(err_payload))),
                    ],
                )
                return [err_payload]

        return prom_app(environ, start_response)

    class CustomServer(ThreadingWSGIServer):
        """Custom ThreadingWSGIServer com suporte para address_family automático."""

    CustomServer.address_family, resolved_addr = _get_best_family(addr, port)
    httpd = make_server(resolved_addr, port, wsgi_app, CustomServer, handler_class=_SilentHandler)

    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    logger.info(f"Servidor de métricas ativo na porta {port} (/metrics e /metrics.json).")
    return httpd
