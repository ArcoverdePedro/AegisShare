from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import FormUserADM, FirstUserForm, ClienteForm
from django.views import View

# from .models import
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


def home(request):
    if request.user.is_authenticated:
        return render(request, "home/homecomlogin.html")
    else:
        return render(request, "home/homesemlogin.html")


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

    return render(request, "registro/login.html", {"redirect_to": redirect_to})


@login_required
def cadastro(request):
    user_permission = request.user.nivel_permissao

    if user_permission not in ("ADM", "FUNC"):
        messages.error(request, "Sem permissão para cadastrar usuários.")
        return redirect("home")

    if request.user.nivel_permissao == "ADM":
        FormUser = FormUserADM
    elif request.user.nivel_permissao == "FUNC":
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


def sobre(request):
    return render(request, "informacoes/sobre.html")


@login_required
def arquivos(request):
    if request.user.nivel_permissao in ('CLI', 'FUNC'):
        return render(request, "arquivos/arquivos_clientes.html")
    else:
        return render(request, "arquivos/meus_arquivos.html")