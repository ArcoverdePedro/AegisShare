from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import CustomUserCreationForm


def home(request):
    if request.user.is_authenticated:
        return render(request, "home/homecomlogin.html")
    else:
        return render(request, "home/homesemlogin.html")


@login_required
def notifications(request):
    return render(request, "notifications/notifications.html")


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


def cadastro(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Cadastro realizado com sucesso!")
            return redirect("home")
        else:
            # Melhorando a exibição de erros do formulário
            for field in form:
                for error in field.errors:
                    # Exibe o erro de forma mais detalhada para o usuário
                    messages.error(request, f"Erro em {field.label}: {error}")
            for error in form.non_field_errors():
                messages.error(request, error)

    else:
        form = CustomUserCreationForm()

    return render(request, "registro/cadastro.html", {"form": form})
