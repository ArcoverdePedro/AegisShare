import sys

from django.core.management import BaseCommand

from aegis_share.services.backup import backup_key, seal


class Command(BaseCommand):
    help = "Cifra stdin para stdout com BACKUP_ENCRYPTION_KEY (ex.: pg_dump -Fc | backup_seal)."

    def handle(self, *args, **options):
        seal(sys.stdin.buffer, sys.stdout.buffer, backup_key())
        sys.stdout.buffer.flush()
