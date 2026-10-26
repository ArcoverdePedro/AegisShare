from cryptography.exceptions import InvalidTag
from django.core.management import BaseCommand, CommandError

from aegis_share.models import FileVersion
from aegis_share.services.files import FileIntegrityError, copy_version_to_local
from aegis_share.services.storage import LOCAL_PREFIX, StorageError


class Command(BaseCommand):
    help = (
        "Copia versoes legadas para FILE_STORAGE_ROOT conferindo hash. "
        "A origem nao e removida; guarde a saida para desativa-la depois."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--encrypt-plaintext",
            action="store_true",
            help="Cifra versoes legadas nao criptografadas durante a copia.",
        )

    def handle(self, *args, **options):
        failures = []
        copied = 0
        versions = FileVersion.objects.exclude(cid__startswith=LOCAL_PREFIX).select_related("file")
        for version in versions.iterator():
            try:
                old = copy_version_to_local(version, encrypt_plaintext=options["encrypt_plaintext"])
            except (FileIntegrityError, StorageError, ValueError, InvalidTag) as exc:
                failures.append(f"{version.id}: {exc}")
                continue
            copied += 1
            self.stdout.write(
                f"migrado version={version.id} origem_cid={old[0]} origem_id={old[1]}"
            )
        self.stdout.write(self.style.SUCCESS(f"{copied} versao(oes) copiada(s)."))
        if failures:
            raise CommandError("Versoes mantidas na origem:\n" + "\n".join(failures))
