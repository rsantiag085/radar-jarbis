"""
Testes unitários para o módulo src/metrics.py.
"""

import json
import unittest
import urllib.request
import prometheus_client

from src import metrics


class TestMetricsModule(unittest.TestCase):
    def test_get_process_memory_rss_bytes(self):
        rss = metrics.get_process_memory_rss_bytes()
        self.assertIsInstance(rss, int)
        self.assertGreater(rss, 0)

    def test_extract_counter_value(self):
        reg = prometheus_client.CollectorRegistry()
        counter = prometheus_client.Counter("test_counter", "desc", registry=reg)
        counter.inc(42)
        self.assertEqual(metrics.extract_counter_value(counter), 42.0)

        gauge = prometheus_client.Gauge("test_gauge", "desc", registry=reg)
        gauge.set(15.5)
        self.assertEqual(metrics.extract_counter_value(gauge), 15.5)

        labeled_counter = prometheus_client.Counter(
            "test_labeled", "desc", ["reason"], registry=reg
        )
        labeled_counter.labels(reason="a").inc(10)
        labeled_counter.labels(reason="b").inc(5)
        self.assertEqual(metrics.extract_counter_value(labeled_counter), 15.0)

        # Objeto inválido deve retornar 0.0 com segurança
        self.assertEqual(metrics.extract_counter_value(None), 0.0)

    def test_dual_metrics_server_endpoints(self):
        port = 18999
        data_to_return = {
            "messages_received": 123,
            "offers_published": 45,
            "offers_filtered": 78,
            "errors_total": 0,
            "memory_rss_bytes": 50000000,
        }

        httpd = metrics.start_metrics_server(
            port=port,
            json_provider=lambda: data_to_return,
            addr="127.0.0.1",
        )

        try:
            # 1. Testa /metrics.json
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics.json", timeout=2) as resp:
                self.assertEqual(resp.status, 200)
                self.assertIn("application/json", resp.headers.get("Content-Type", ""))
                body = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(body["messages_received"], 123)
                self.assertEqual(body["offers_published"], 45)
                self.assertEqual(body["memory_rss_bytes"], 50000000)

            # 2. Testa /metrics (Prometheus padrão)
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=2) as resp:
                self.assertEqual(resp.status, 200)
                self.assertIn("text/plain", resp.headers.get("Content-Type", ""))
                text = resp.read().decode("utf-8")
                self.assertTrue(len(text) > 0)

            # 3. Testa /metrics/<key> (Plain text para Zabbix)
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics/messages_received", timeout=2) as resp:
                self.assertEqual(resp.status, 200)
                self.assertIn("text/plain", resp.headers.get("Content-Type", ""))
                val = resp.read().decode("utf-8")
                self.assertEqual(val, "123")
        finally:
            httpd.shutdown()
