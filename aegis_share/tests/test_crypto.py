import base64
import secrets

from cryptography.exceptions import InvalidTag
from django.test import SimpleTestCase, override_settings

from aegis_share.services.crypto import (
    decrypt_file,
    decrypt_secret,
    encrypt_file,
    encrypt_secret,
    sha256_hex,
)

TEST_KEY = base64.urlsafe_b64encode(b"k" * 32).decode()


@override_settings(FILE_ENCRYPTION_KEY=TEST_KEY)
class CryptoTests(SimpleTestCase):
    def test_file_round_trip_and_hashes(self):
        content = b"conteudo confidencial do AegisShare"
        aad = b"file-version:test"

        encrypted, wrapped_key, plain_hash, encrypted_hash = encrypt_file(
            content, aad=aad
        )

        self.assertNotEqual(encrypted, content)
        self.assertTrue(encrypted.startswith(b"AEGIS1"))
        self.assertEqual(plain_hash, sha256_hex(content))
        self.assertEqual(encrypted_hash, sha256_hex(encrypted))
        self.assertEqual(decrypt_file(encrypted, wrapped_key, aad=aad), content)

    def test_modified_ciphertext_is_rejected(self):
        encrypted, wrapped_key, _, _ = encrypt_file(b"original", aad=b"aad")
        modified = bytearray(encrypted)
        modified[-1] ^= 1

        with self.assertRaises(InvalidTag):
            decrypt_file(bytes(modified), wrapped_key, aad=b"aad")

    def test_wrong_aad_is_rejected(self):
        encrypted, wrapped_key, _, _ = encrypt_file(b"original", aad=b"correct")
        with self.assertRaises(InvalidTag):
            decrypt_file(encrypted, wrapped_key, aad=b"wrong")

    def test_secret_round_trip(self):
        secret = secrets.token_urlsafe(20)
        encrypted = encrypt_secret(secret, purpose="totp:test")
        self.assertNotEqual(encrypted, secret)
        self.assertEqual(
            decrypt_secret(encrypted, purpose="totp:test"),
            secret,
        )
