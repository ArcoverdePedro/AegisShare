from django.db import migrations


def backfill_legacy_versions(apps, schema_editor):
    IPFSFile = apps.get_model("aegis_share", "IPFSFile")
    FileVersion = apps.get_model("aegis_share", "FileVersion")

    for file in IPFSFile.objects.all().iterator():
        if FileVersion.objects.filter(file_id=file.pk).exists():
            continue

        version = FileVersion.objects.create(
            file_id=file.pk,
            version_number=1,
            cid=file.cid,
            pinata_id=file.pinata_id or "",
            mime_type=file.mime_type or "application/octet-stream",
            original_size=file.tamanho_arquivo,
            encrypted_size=file.tamanho_arquivo,
            sha256="",
            encrypted_sha256="",
            is_encrypted=False,
            wrapped_key="",
            uploaded_by_id=None,
        )

        if file.data_adicionado:
            FileVersion.objects.filter(pk=version.pk).update(
                created_at=file.data_adicionado
            )


class Migration(migrations.Migration):
    dependencies = [
        ("aegis_share", "0002_apitoken_documentrequest_documentrequestitem_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_legacy_versions, migrations.RunPython.noop),
    ]
