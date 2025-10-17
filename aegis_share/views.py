from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import FormUserADM, FirstUserForm, ClienteForm, IPFSForm, CustomUser
from django.views import View
import requests
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from dotenv import load_dotenv
import os

# from .models import
from django.contrib.auth import get_user_model

User = get_user_model()

load_dotenv()


class FirstSuperuserCreateView(View):
    template_name = "primeiro_cadastro.html"

    def get(self, request):
        if User.objects.filter(is_superuser=True).exists():
            return redirect("home")

        form = FirstUserForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = FirstUserForm(request.POST)

        if User.objects.filter(is_superuser=True).exists():
            return redirect("home")

        if form.is_valid():
            user = form.save()

            login(request, user)
            return redirect("home")

        return render(request, self.template_name, {"form": form})


def uploadipfs(filepath):
    url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
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
            response.raise_for_status()  # levanta erro se status != 2xx
            data = response.json()
            return JsonResponse({"success": True, "pinata_response": data})

        except requests.RequestException as e:
            return JsonResponse({"success": False, "error": str(e)}, status=500)

    return JsonResponse({"error": "Método não permitido"}, status=405)

@login_required
def buscar_cliente(request):
    term = request.GET.get('term', '')
    clientes = CustomUser.objects.filter(nivel_permissao="CLI").filter(username__icontains=term)[:10]
    results = [{"id": c.id, "nome": c.username, "cpf": c.cpf} for c in clientes]
    return JsonResponse(results, safe=False)


def home(request):
    if request.user.is_authenticated:
        return render(request, "home/homecomlogin.html")
    else:
        return render(request, "home/homesemlogin.html")


def sobre(request):
    return render(request, "informacoes/sobre.html")


def custom_login(request):
    redirect_to = request.POST.get("next") or request.GET.get("next")
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, "Login realizado com sucesso!")
            if redirect_to:
                return redirect(redirect_to)
            else:
                return redirect("home")
        else:
            messages.error(request, "Usuário ou senha inválidos.")
            return redirect("login")

    return render(request, "registro/login.html", {"redirect_to": redirect_to})


@login_required
def cadastro(request):
    if request.user.nivel_permissao == "CLI":
        messages.error(request, "Sem permissão para essa página.")
        return redirect("home")

    if request.user.nivel_permissao == "ADM":
        FormUser = FormUserADM
    else:
        FormUser = ClienteForm

    form = FormUser()

    if request.method == "POST":
        form = FormUser(request.POST)

        if form.is_valid():
            user = form.save()
            messages.success(request, f"Usuário '{user.username}' Cadastrado!")
            return redirect("cadastro")
        else:
            for field in form:
                for error in field.errors:
                    messages.error(request, f"Erro em {field.label}: {error}")

            for error in form.non_field_errors():
                messages.error(request, error)

    return render(request, "registro/cadastro.html", {"form": form})


@login_required
def notifications(request):
    return render(request, "notifications/notifications.html")


@login_required
def arquivos(request, id):
    return render(request, "arquivos/arquivos.html")


@login_required
def upload(request):
    if request.user.nivel_permissao == "CLI":
        messages.error(request, "Sem permissão para essa página.")
        return redirect("home")

    if request.method == "POST":
        form = IPFSForm(request.POST, request.FILES)

        if form.is_valid():
            arquivo = form.cleaned_data["arquivo"]
            temp_path = f"/tmp/{arquivo.name}"

            # salva temporariamente o arquivo
            with open(temp_path, "wb+") as f:
                for chunk in arquivo.chunks():
                    f.write(chunk)

            # envia para o Pinata
            ipfs_file = uploadipfs(temp_path)

            return JsonResponse(
                {
                    "mensagem": "Upload feito com sucesso!",
                    "cid": ipfs_file.cid,
                    "nome": ipfs_file.nome_arquivo,
                    "mime_type": ipfs_file.mime_type,
                    "tamanho": ipfs_file.tamanho_arquivo,
                }
            )

    else:
        form = IPFSForm()

    return render(request, "arquivos/upload.html", {"form": form})


@login_required
def user(request):
    return render(request, "user/user.html")
