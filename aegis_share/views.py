from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import FormUserADM, FirstUserForm, ClienteForm, IPFSForm, CustomUser
from .models import IPFSFile, CustomUser
from django.views import View
from django.http import JsonResponse
from .utils import gerar_link_pinata, uploadipfs, dar_acesso, get_arquivos_por_permissao
from django.contrib.auth import get_user_model

User = get_user_model()


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
def arquivos(request):
    context = {}
    user = request.user
    context["arquivos"] = get_arquivos_por_permissao(user)

    return render(request, "arquivos/arquivos.html", context)


@login_required
def upload(request):
    if request.user.nivel_permissao == "CLI":
        messages.error(request, "Sem permissão para essa página.")
        return redirect("home")

    if request.method == "POST":
        form = IPFSForm(request.POST, request.FILES)

        if form.is_valid():
            dono_arquivo = CustomUser.objects.get(id=form.cleaned_data["cliente_id"])
            arquivo = form.cleaned_data["arquivo"]
            arq_temp = f"/tmp/{arquivo.name}"

            with open(arq_temp, "wb+") as f:
                for chunk in arquivo.chunks():
                    f.write(chunk)

            ipfs_file = uploadipfs(arq_temp)


            if isinstance(ipfs_file, int):
                messages.error(request, f"Request deu erro no Servidor: {ipfs_file}")
            else:
                if "data" in ipfs_file:
                    dados = ipfs_file["data"]
                    id_arquivo = dados["id"]
                    nome = dados["name"]
                    cid = dados["cid"]
                    tamanho = dados["size"]
                    mime_type = dados["mime_type"]
                    arq_upload = IPFSFile.objects.create(
                        pinata_id=id_arquivo,
                        cid=cid,
                        nome_arquivo=nome,
                        tamanho_arquivo=tamanho,
                        mime_type=mime_type,
                        dono_arquivo=dono_arquivo,
                    )
                    if request.user.nivel_permissao == "FUNC":
                        dar_acesso(arquivo=arq_upload, usuario_alvo=request.user)
                    messages.success(request, "Arquivo enviado com sucesso!")
                else:
                    messages.error(request, "Resposta inesperada do Pinata")
    else:
        form = IPFSForm()

    return render(request, "arquivos/upload.html", {"form": form})

@login_required
def user(request):
    return render(request, "user/user.html")
