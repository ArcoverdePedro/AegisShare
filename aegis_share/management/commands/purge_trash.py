from django.conf import settings
from django.core.management import BaseCommand, CommandError

from aegis_share.services.files import purge_expired_trash


class Command(BaseCommand):
    help = "Remove definitivamente arquivos da lixeira apos o periodo de retencao."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=settings.FILE_RETENTION_DAYS,
            help="Dias de retencao antes do expurgo.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        if days < 1:
            raise CommandError("--days deve ser maior que zero.")
        purged, failures = purge_expired_trash(days)
        self.stdout.write(self.style.SUCCESS(f"{purged} arquivo(s) removido(s) definitivamente."))
        if failures:
            raise CommandError(
                "Alguns objetos nao foram removidos da Pinata; registros locais foram preservados: "
                + ", ".join(failures)
            )
