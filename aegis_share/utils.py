import base64
import os
import re
from io import BytesIO

import requests
from dotenv import load_dotenv
from PIL import Image

from .models import FileAccess, IPFSFile

load_dotenv()


def uploadipfs(filepath):
    url = "https://uploads.pinata.cloud/v3/files"
    headers = {"Authorization": f"Bearer {os.getenv('PINATA_JWT_TOKEN')}"}

    with open(filepath, "rb") as file:
        response = requests.post(url, files={"file": file}, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            return response.status_code


def dar_acesso(arquivo, usuario_alvo):
    FileAccess.objects.get_or_create(arquivo=arquivo, user=usuario_alvo)


def arquivos_por_permissao(user):
    if user.is_admin():
        return IPFSFile.objects.all().order_by("-data_adicionado")

    elif user.nivel_permissao == "FUNC":
        return IPFSFile.objects.filter(usuarios_permitidos=user).order_by(
            "-data_adicionado"
        )

    else:
        return IPFSFile.objects.filter(dono_arquivo=user).order_by("-data_adicionado")


def limpar_strings(string_com_formatacao):
    """
    Remove todos os caracteres que não são dígitos.
    """
    if not string_com_formatacao:
        return ""

    return re.sub(r"[^0-9]", "", string_com_formatacao)


def imagem_para_base64(arquivo_imagem):
    """
    Conversão direta para AVIF base64
    """
    img = Image.open(arquivo_imagem).convert("RGB")

    buffer = BytesIO()
    img.save(buffer, format="AVIF", quality=80)

    base64_str = base64.b64encode(buffer.getvalue()).decode()

    return f"data:image/avif;base64,{base64_str}"
