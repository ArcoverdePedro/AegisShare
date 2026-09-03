import logging
import socket
import struct

from django.conf import settings

logger = logging.getLogger(__name__)


class MalwareDetected(ValueError):
    pass


class AntivirusUnavailable(RuntimeError):
    pass


def scan_bytes(content: bytes) -> None:
    """Usa o protocolo INSTREAM do clamd sem adicionar biblioteca cliente."""
    if not settings.CLAMAV_ENABLED:
        return

    try:
        with socket.create_connection(
            (settings.CLAMAV_HOST, settings.CLAMAV_PORT), timeout=5
        ) as sock:
            sock.settimeout(30)
            sock.sendall(b"zINSTREAM\0")
            chunk_size = 1024 * 1024
            for offset in range(0, len(content), chunk_size):
                chunk = content[offset : offset + chunk_size]
                sock.sendall(struct.pack("!I", len(chunk)))
                sock.sendall(chunk)
            sock.sendall(struct.pack("!I", 0))

            response = b""
            while True:
                part = sock.recv(4096)
                if not part:
                    break
                response += part
                if b"\0" in part:
                    break
    except OSError as exc:
        logger.exception("clamav_unavailable")
        if settings.CLAMAV_REQUIRED:
            raise AntivirusUnavailable("ClamAV indisponivel e CLAMAV_REQUIRED=true.") from exc
        return

    result = response.decode(errors="replace").strip("\x00\r\n")
    if "FOUND" in result:
        signature = result.split("FOUND", 1)[0].split(":", 1)[-1].strip()
        logger.warning("malware_detected", extra={"signature": signature})
        raise MalwareDetected(f"Arquivo bloqueado pelo antivirus: {signature or 'ameaca detectada'}")
    if "OK" not in result:
        logger.error("clamav_invalid_response", extra={"response": result})
        if settings.CLAMAV_REQUIRED:
            raise AntivirusUnavailable("Resposta inesperada do ClamAV.")
