#!/usr/bin/env python3
import argparse
import base64
import os
import secrets
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

KEY_NAMES = (
    "WEBPUSH_VAPID_PUBLIC_KEY",
    "WEBPUSH_VAPID_PRIVATE_KEY",
    "WEBPUSH_VAPID_SUBJECT",
)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _generate_key_pair() -> tuple[str, str]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_der = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_point = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return _b64url(public_point), _b64url(private_der)


def _is_placeholder(value: str) -> bool:
    normalized = value.strip().strip('"').strip("'")
    return not normalized or normalized.startswith("CHANGE_ME")


def _atomic_write_private(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(6)}.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _read_positions(lines: list[str], path: Path) -> dict[str, tuple[int, str]]:
    positions: dict[str, tuple[int, str]] = {}
    for index, line in enumerate(lines):
        candidate = line.rstrip("\r\n")
        if not candidate or candidate.lstrip().startswith("#") or "=" not in candidate:
            continue
        key, value = candidate.split("=", 1)
        key = key.strip()
        if key not in KEY_NAMES:
            continue
        if key in positions:
            raise SystemExit(
                f"{path} possui mais de uma definicao de {key}. Corrija a duplicidade."
            )
        positions[key] = (index, value)
    return positions


def _set_value(
    lines: list[str],
    positions: dict[str, tuple[int, str]],
    key: str,
    value: str,
) -> None:
    position = positions.get(key)
    if position is None:
        if lines and not lines[-1].endswith(("\n", "\r")):
            lines[-1] += "\n"
        lines.append(f"{key}={value}\n")
        positions[key] = (len(lines) - 1, value)
        return

    index, _ = position
    newline = "\r\n" if lines[index].endswith("\r\n") else "\n"
    lines[index] = f"{key}={value}{newline}"
    positions[key] = (index, value)


def install(path: Path, *, subject: str | None, rotate: bool) -> list[str]:
    if not path.exists() or not path.is_file():
        raise SystemExit(
            f"{path} nao existe. Crie-o a partir de .env-example antes de gerar VAPID."
        )

    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    positions = _read_positions(lines, path)
    current_public = positions.get("WEBPUSH_VAPID_PUBLIC_KEY", (-1, ""))[1]
    current_private = positions.get("WEBPUSH_VAPID_PRIVATE_KEY", (-1, ""))[1]
    public_present = not _is_placeholder(current_public)
    private_present = not _is_placeholder(current_private)

    if public_present != private_present and not rotate:
        raise SystemExit(
            "O .env possui somente uma das chaves VAPID. Use --rotate para gerar um par coerente."
        )

    changed: list[str] = []
    if rotate or not (public_present and private_present):
        public_key, private_key = _generate_key_pair()
        _set_value(lines, positions, "WEBPUSH_VAPID_PUBLIC_KEY", public_key)
        _set_value(lines, positions, "WEBPUSH_VAPID_PRIVATE_KEY", private_key)
        changed.extend(["WEBPUSH_VAPID_PUBLIC_KEY", "WEBPUSH_VAPID_PRIVATE_KEY"])

    current_subject = positions.get("WEBPUSH_VAPID_SUBJECT", (-1, ""))[1]
    if _is_placeholder(current_subject):
        if not subject:
            raise SystemExit(
                "Informe --subject mailto:contato@dominio ou uma URL https:// valida."
            )
        if not subject.startswith(("mailto:", "https://")):
            raise SystemExit("--subject deve iniciar com mailto: ou https://.")
        _set_value(lines, positions, "WEBPUSH_VAPID_SUBJECT", subject)
        changed.append("WEBPUSH_VAPID_SUBJECT")

    if changed:
        _atomic_write_private(path, "".join(lines))
    else:
        os.chmod(path, 0o600)
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera e instala chaves VAPID sem imprimir a chave privada no terminal."
    )
    parser.add_argument("--install-env", required=True, metavar="ARQUIVO")
    parser.add_argument(
        "--subject",
        help="identidade VAPID, por exemplo mailto:ti@hospital.org.br",
    )
    parser.add_argument(
        "--rotate",
        action="store_true",
        help="gera um novo par VAPID; subscriptions existentes precisarao ser renovadas",
    )
    args = parser.parse_args()

    env_path = Path(args.install_env).expanduser().resolve()
    changed = install(env_path, subject=args.subject, rotate=args.rotate)
    if changed:
        print(
            f"Configuracao Web Push instalada com seguranca em {env_path} (permissao 0600): "
            + ", ".join(changed)
        )
    else:
        print("Configuracao Web Push existente preservada; nenhuma chave foi rotacionada.")


if __name__ == "__main__":
    main()
