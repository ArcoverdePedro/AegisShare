from django.db.models import Q
from django.utils import timezone
import requests
from dotenv import load_dotenv
import os
from django.http import JsonResponse
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


def gerar_link_pinata(request):
    if request.method == "POST":
        url = "https://api.pinata.cloud/v3/files/private/download_link"

        payload = {
            "url": "https://example.mypinata.cloud/files/bafybeifq444z4b7yqzcyz4a5gspb2rpyfcdxp3mrfpigmllh52ld5tyzwm",
            "expires": 500000,
            "date": int(timezone.now().timestamp()),
            "method": "GET",
        }

        headers = {
            "Authorization": f"Bearer {os.getenv('PINATA_JWT_TOKEN')}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return JsonResponse({"success": True, "pinata_response": data})

        except requests.RequestException as e:
            return JsonResponse({"success": False, "error": str(e)}, status=500)

    return JsonResponse({"error": "Método não permitido"}, status=405)


def dar_acesso(arquivo, usuario_alvo):
    FileAccess.objects.get_or_create(arquivo=arquivo, user=usuario_alvo)

def get_arquivos_por_permissao(user):
    
    if user.is_admin():
        return IPFSFile.objects.all()
    
    elif user.nivel_permissao == "FUNC":
        return IPFSFile.objects.filter(usuarios_permitidos=user)
    
    else:
        return IPFSFile.objects.filter(dono_arquivo=user)
