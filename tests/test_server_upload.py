import os
from unittest import TestCase
from unittest.mock import patch

from flet_web.uploads import build_upload_url

from server import configurar_chave_upload


class ServerUploadTest(TestCase):
    def test_configures_secret_and_builds_signed_upload_url(self):
        with patch.dict(os.environ, {}, clear=True):
            secret = configurar_chave_upload()
            self.assertGreaterEqual(len(secret), 32)
            url = build_upload_url("/upload", "arquivo.txt", 600, None)
            self.assertIn("f=arquivo.txt", url)
            self.assertIn("&s=", url)

    def test_preserves_explicit_secret(self):
        with patch.dict(os.environ, {"FLET_SECRET_KEY": "chave-configurada"}, clear=True):
            self.assertEqual(configurar_chave_upload(), "chave-configurada")
