import base64
from io import BytesIO

from django.test import SimpleTestCase, override_settings

from aegis_share.services.backup import MAGIC, PREFIX_SIZE, BackupError, backup_key, seal, unseal
from aegis_share.services.crypto import CryptoConfigurationError

KEY = b"k" * 32
DATA = bytes(range(256)) * 40  # 10240 bytes -> 3 blocos de 4096


def sealed(data=DATA, key=KEY):
    out = BytesIO()
    seal(BytesIO(data), out, key, chunk_size=4096)
    return out.getvalue()


def opened(blob, key=KEY):
    out = BytesIO()
    unseal(BytesIO(blob), out, key)
    return out.getvalue()


def blocks(blob):
    header, rest, parts = blob[: len(MAGIC) + PREFIX_SIZE], blob[len(MAGIC) + PREFIX_SIZE :], []
    while rest:
        size = 4 + int.from_bytes(rest[:4], "big")
        parts.append(rest[:size])
        rest = rest[size:]
    return header, parts


class BackupCryptoTests(SimpleTestCase):
    def test_roundtrip_including_empty_input(self):
        blob = sealed()
        self.assertNotIn(DATA[:64], blob)
        self.assertEqual(opened(blob), DATA)
        self.assertEqual(opened(sealed(b"")), b"")

    def test_tampering_truncation_reordering_and_wrong_key_fail(self):
        header, parts = blocks(sealed())
        self.assertEqual(len(parts), 3)
        flipped = bytearray(sealed())
        flipped[-1] ^= 1
        attacks = [
            bytes(flipped),
            header + b"".join(parts[:2]),  # bloco final removido
            header + parts[1] + parts[0] + parts[2],
            sealed() + b"x",
        ]
        for blob in attacks:
            with self.subTest(size=len(blob)), self.assertRaises(BackupError):
                opened(blob)
        with self.assertRaises(BackupError):
            opened(sealed(), key=b"z" * 32)

    def test_backup_key_must_differ_from_file_key(self):
        key = base64.urlsafe_b64encode(KEY).decode()
        same = override_settings(BACKUP_ENCRYPTION_KEY=key, FILE_ENCRYPTION_KEY=key)
        with same, self.assertRaises(CryptoConfigurationError):
            backup_key()
        with (
            override_settings(BACKUP_ENCRYPTION_KEY=""),
            self.assertRaises(CryptoConfigurationError),
        ):
            backup_key()
