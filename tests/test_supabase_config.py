"""Testes unitários da configuração opcional do Supabase."""

import os
import unittest
from unittest.mock import patch

from src.config import SupabaseConfig


class TestSupabaseConfig(unittest.TestCase):
    def test_disabled_by_default_without_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            config = SupabaseConfig.from_env()

        self.assertFalse(config.enabled)
        self.assertFalse(config.required)
        self.assertIsNone(config.url)
        self.assertIsNone(config.service_role_key)

    def test_disabled_does_not_validate_credentials(self):
        with patch.dict(
            os.environ,
            {
                "SUPABASE_ENABLED": "false",
                "SUPABASE_URL": "not-a-url",
            },
            clear=True,
        ):
            config = SupabaseConfig.from_env()

        self.assertFalse(config.enabled)

    def test_enabled_requires_url_and_service_role_key(self):
        with patch.dict(
            os.environ,
            {"SUPABASE_ENABLED": "true"},
            clear=True,
        ):
            with self.assertRaises(RuntimeError) as context:
                SupabaseConfig.from_env()

        message = str(context.exception)
        self.assertIn("SUPABASE_URL", message)
        self.assertIn("SUPABASE_SERVICE_ROLE_KEY", message)

    def test_enabled_accepts_valid_configuration(self):
        with patch.dict(
            os.environ,
            {
                "SUPABASE_ENABLED": "true",
                "SUPABASE_REQUIRED": "true",
                "SUPABASE_URL": "https://example.supabase.co",
                "SUPABASE_SERVICE_ROLE_KEY": "test-only-key",
            },
            clear=True,
        ):
            config = SupabaseConfig.from_env()

        self.assertTrue(config.enabled)
        self.assertTrue(config.required)

    def test_validation_error_never_contains_credentials(self):
        credential = "test-only-sensitive-value"
        with patch.dict(
            os.environ,
            {
                "SUPABASE_ENABLED": "true",
                "SUPABASE_URL": "invalid-url",
                "SUPABASE_SERVICE_ROLE_KEY": credential,
            },
            clear=True,
        ):
            with self.assertRaises(RuntimeError) as context:
                SupabaseConfig.from_env()

        self.assertNotIn(credential, str(context.exception))
        self.assertNotIn(credential, repr(context.exception))

    def test_repr_hides_url_and_service_role_key(self):
        credential = "test-only-sensitive-value"
        url = "https://example.supabase.co"
        config = SupabaseConfig(
            enabled=True,
            required=False,
            url=url,
            service_role_key=credential,
        )

        representation = repr(config)
        self.assertNotIn(url, representation)
        self.assertNotIn(credential, representation)


if __name__ == "__main__":
    unittest.main(verbosity=2)
