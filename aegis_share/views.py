from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import CustomUserCreationForm, FirstUserForm, ClienteForm
from django.urls import reverse
from django.views import View
from .models import UsersInfos
from django.contrib.auth import get_user_model

User = get_user_model()


class FirstSuperuserCreateView(View):
    template_name = 'primeiro_cadastro.html'

    def get(self, request):
        if User.objects.filter(is_superuser=True).exists():
            return redirect('home')

        form = FirstUserForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = FirstUserForm(request.POST)

        if User.objects.filter(is_superuser=True).exists():
            return redirect('home')

        if form.is_valid():
            user = form.save(commit=False)
            user.is_staff = True
            user.is_superuser = True
            user.save()

            login(request, user)

            return redirect('home')

        return render(request, self.template_name, {'form': form})


def home(request):
    if request.user.is_authenticated:
        return render(request, "home/homecomlogin.html")
    else:
        return render(request, "home/homesemlogin.html")


def custom_login(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, "Login realizado com sucesso!")
            return redirect("home")
        else:
            messages.error(request, "Usuário ou senha inválidos.")

    return render(request, "registro/login.html")


@login_required
def cadastro(request):

    if request.user.usersinfos.nivel_permissao == 'ADM':
        form = CustomUserCreationForm()
    elif request.user.usersinfos.nivel_permissao == 'FUNC':
        form = ClienteForm()

    if request.method == "POST":
        if request.user.usersinfos.nivel_permissao == 'ADM':
            form = CustomUserCreationForm(request.POST)
        elif request.user.usersinfos.nivel_permissao == 'FUNC':
            form = ClienteForm(request.POST)

        if form.is_valid():
            messages.success(request, "Cadastro realizado com sucesso!")
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
