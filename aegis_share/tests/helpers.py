from aegis_share.models import CustomUser, IPFSFile


def make_user(username, *, role="CLI", password="StrongTestPass123!"):
    return CustomUser.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password=password,
        nivel_permissao=role,
    )


def make_file(owner, *, cid="bafy-test-cid", name="documento.pdf"):
    return IPFSFile.objects.create(
        pinata_id="pinata-test-id",
        cid=cid,
        nome_arquivo=name,
        mime_type="application/pdf",
        tamanho_arquivo=1024,
        dono_arquivo=owner,
    )
