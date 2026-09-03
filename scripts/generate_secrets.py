#!/usr/bin/env python3
import argparse
import base64
import os
import secrets
from pathlib import Path


def _secret_contents() -> str:
    secret_key = secrets.token_urlsafe(64)
    file_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")
    return f"SECRET_KEY={secret_key}\nFILE_ENCRYPTION_KEY={file_key}\n"


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
    except Exception:
        try:
            path.unlink(missing_ok=True)
        finally:
            raise

    os.chmod(path, 0o600)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera SECRET_KEY e FILE_ENCRYPTION_KEY sem expo-las no stdout."
    )
    parser.add_argument(
        "--output",
        default=".secrets.generated.env",
        help="arquivo de destino (padrao: .secrets.generated.env)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="permite substituir o arquivo de destino existente",
    )
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_private_file(output, force=args.force)

    print(f"Segredos gerados em {output} com permissao 0600.")
    print("Copie-os para o seu gerenciador de segredos/.env e remova o arquivo quando terminar.")


if __name__ == "__main__":
    main()
