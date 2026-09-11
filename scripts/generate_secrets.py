#!/usr/bin/env python3
import argparse
import base64
import os
import secrets
from pathlib import Path

SECRET_KEYS = ("SECRET_KEY", "FILE_ENCRYPTION_KEY")


def _generate_secrets() -> dict[str, str]:
    return {
        "SECRET_KEY": secrets.token_urlsafe(64),
        "FILE_ENCRYPTION_KEY": base64.urlsafe_b64encode(
            secrets.token_bytes(32)
        ).decode("ascii"),
    }


def _secret_contents(values: dict[str, str] | None = None) -> str:
    values = values or _generate_secrets()
    return "".join(f"{key}={values[key]}\n" for key in SECRET_KEYS)


def _write_private_file(path: Path, *, force: bool) -> None:
    flags = os.O_WRONLY | os.O_CREAT
    flags |= os.O_TRUNC if force else os.O_EXCL

    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise SystemExit(
            f"{path} ja existe. Use --force somente se quiser substituir as chaves."
        ) from exc

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(_secret_contents())
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink(missing_ok=True)
        finally:
            raise

    os.chmod(path, 0o600)


def _is_placeholder(value: str) -> bool:
    value = value.strip().strip('"').strip("'")
    return not value or value.startswith("CHANGE_ME")


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


def _install_into_env(path: Path) -> list[str]:
    if not path.exists():
        raise SystemExit(
            f"{path} nao existe. Crie-o a partir de .env-example antes de instalar os segredos."
        )
    if not path.is_file():
        raise SystemExit(f"{path} nao e um arquivo regular.")

    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    positions: dict[str, tuple[int, str]] = {}

    for index, line in enumerate(lines):
        candidate = line.rstrip("\r\n")
        if not candidate or candidate.lstrip().startswith("#") or "=" not in candidate:
            continue
        key, value = candidate.split("=", 1)
        key = key.strip()
        if key not in SECRET_KEYS:
            continue
        if key in positions:
            raise SystemExit(
                f"{path} possui mais de uma definicao de {key}. Corrija a duplicidade antes de continuar."
            )
        positions[key] = (index, value)

    generated = _generate_secrets()
    changed: list[str] = []

    for key in SECRET_KEYS:
        position = positions.get(key)
        if position is None:
            if lines and not lines[-1].endswith(("\n", "\r")):
                lines[-1] += "\n"
            lines.append(f"{key}={generated[key]}\n")
            changed.append(key)
            continue

        index, current_value = position
        if not _is_placeholder(current_value):
            continue

        newline = "\r\n" if lines[index].endswith("\r\n") else "\n"
        lines[index] = f"{key}={generated[key]}{newline}"
        changed.append(key)

    if changed:
        _atomic_write_private(path, "".join(lines))
    else:
        os.chmod(path, 0o600)

    return changed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera SECRET_KEY e FILE_ENCRYPTION_KEY sem expo-las no stdout."
    )
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument(
        "--output",
        help="arquivo privado de destino (padrao: .secrets.generated.env)",
    )
    destination.add_argument(
        "--install-env",
        metavar="ARQUIVO",
        help=(
            "substitui apenas SECRET_KEY/FILE_ENCRYPTION_KEY vazias ou CHANGE_ME "
            "no arquivo informado, sem rotacionar valores validos"
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="permite substituir o arquivo usado por --output",
    )
    args = parser.parse_args()

    if args.install_env:
        if args.force:
            parser.error("--force nao pode ser usado com --install-env")
        env_path = Path(args.install_env).expanduser().resolve()
        changed = _install_into_env(env_path)
        if changed:
            print(
                f"Segredos instalados com seguranca em {env_path} (permissao 0600): "
                + ", ".join(changed)
            )
        else:
            print(
                f"Nenhum segredo foi alterado em {env_path}; os valores existentes foram preservados."
            )
        return

    output = Path(args.output or ".secrets.generated.env").expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_private_file(output, force=args.force)

    print(f"Segredos gerados em {output} com permissao 0600.")
    print("Copie-os para o seu gerenciador de segredos/.env e remova o arquivo quando terminar.")


if __name__ == "__main__":
    main()
