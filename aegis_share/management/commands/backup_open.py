import sys

from django.core.management import BaseCommand, CommandError

from aegis_share.services.backup import BackupError, backup_key, unseal


class Command(BaseCommand):
    help = "Decifra e autentica um backup de stdin para stdout; falha em corrupcao ou truncamento."

    def handle(self, *args, **options):
        try:
            unseal(sys.stdin.buffer, sys.stdout.buffer, backup_key())
        except BackupError as exc:
            raise CommandError(str(exc)) from exc
        sys.stdout.buffer.flush()
