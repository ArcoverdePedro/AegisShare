import base64
import os
import secrets
from pathlib import Path

from django.core.management import BaseCommand, CommandError
from django.core.management.utils import get_random_secret_key


class Command(BaseCommand):
    help = "Gera SECRET_KEY e FILE_ENCRYPTION_KEY em arquivo privado, sem expo-las no stdout."

    def add_arguments(self, parser):
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

    def handle(self, *args, **options):
        output = Path(options["output"]).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)

        flags = os.O_WRONLY | os.O_CREAT
        flags |= os.O_TRUNC if options["force"] else os.O_EXCL

        try:
            fd = os.open(output, flags, 0o600)
        except FileExistsError as exc:
            raise CommandError(
                f"{output} ja existe. Use --force somente se quiser substituir as chaves."
            ) from exc

        file_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")
        contents = (
            f"SECRET_KEY={get_random_secret_key()}\n"
            f"FILE_ENCRYPTION_KEY={file_key}\n"
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(contents)
        except Exception:
            try:
                output.unlink(missing_ok=True)
            finally:
                raise

        os.chmod(output, 0o600)
        self.stdout.write(self.style.SUCCESS(f"Segredos gerados em {output} com permissao 0600."))
        self.stdout.write(
            "Copie-os para o seu gerenciador de segredos/.env e remova o arquivo quando terminar."
        )
