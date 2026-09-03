import base64
import secrets

from django.core.management import BaseCommand
from django.core.management.utils import get_random_secret_key


class Command(BaseCommand):
    help = "Gera SECRET_KEY e FILE_ENCRYPTION_KEY adequadas para producao."

    def handle(self, *args, **options):
        file_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
        self.stdout.write(f"SECRET_KEY={get_random_secret_key()}")
        self.stdout.write(f"FILE_ENCRYPTION_KEY={file_key}")
        self.stdout.write(
            self.style.WARNING(
                "Guarde FILE_ENCRYPTION_KEY em um gerenciador de segredos. Perde-la impede descriptografar novos arquivos."
            )
        )
