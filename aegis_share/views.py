from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages


def home(request):
    ...
    return render(request, "home/home.html")


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
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Cadastro realizado com sucesso!")
            return redirect("home")
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = UserCreationForm()

    return render(request, "registro/cadastro.html", {"form": form})
