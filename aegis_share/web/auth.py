from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from aegis_share.forms import ClienteForm, FirstUserForm, FormUserADM, FotoForm, TOTPCodeForm
from aegis_share.services.security import consume_recovery_code, verify_totp
from aegis_share.utils import imagem_para_base64

User = get_user_model()


def _safe_next(request, value):
    if value and url_has_allowed_host_and_scheme(
        value,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return value
    return reverse("home")


def _rate_key(prefix, request, username=""):
    return f"{prefix}:{request.META.get('REMOTE_ADDR', 'unknown')}:{username.lower()}"


class FirstSuperuserCreateView(View):
    template_name = "primeiro_cadastro.html"

    def dispatch(self, request, *args, **kwargs):
        if User.objects.filter(is_superuser=True).exists():
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return render(request, self.template_name, {"form": FirstUserForm()})

    def post(self, request):
        form = FirstUserForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Administrador inicial criado com sucesso.")
            return redirect("home")
        return render(request, self.template_name, {"form": form})


def custom_login(request):
    redirect_to = request.POST.get("next") or request.GET.get("next")
    if request.method != "POST":
        return render(request, "registro/login.html", {"redirect_to": redirect_to})

    username = request.POST.get("username", "").strip()
    password = request.POST.get("password", "")
    key = _rate_key("login", request, username)
    attempts = int(cache.get(key, 0))
    if attempts >= 10:
        messages.error(request, "Muitas tentativas. Aguarde alguns minutos e tente novamente.")
        return redirect("login")

    user = authenticate(request, username=username, password=password)
    if user is None:
        cache.set(key, attempts + 1, 300)
        messages.error(request, "Usuario ou senha invalidos.")
        return redirect("login")

    cache.delete(key)
    security = getattr(user, "security_settings", None)
    if security and security.totp_enabled:
        request.session.cycle_key()
        request.session["pending_2fa_user"] = str(user.id)
        request.session["pending_2fa_next"] = _safe_next(request, redirect_to)
        return redirect("login_2fa")

    login(request, user)
    messages.success(request, "Login realizado com sucesso!")
    return redirect(_safe_next(request, redirect_to))


def login_2fa(request):
    pending_user_id = request.session.get("pending_2fa_user")
    if not pending_user_id:
        return redirect("login")

    user = User.objects.filter(id=pending_user_id, is_active=True).first()
    if not user:
        request.session.pop("pending_2fa_user", None)
        return redirect("login")

    form = TOTPCodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        key = _rate_key("login-2fa", request, user.username)
        attempts = int(cache.get(key, 0))
        if attempts >= 8:
            messages.error(request, "Muitas tentativas de 2FA. Aguarde alguns minutos.")
            return render(request, "registro/login_2fa.html", {"form": form})

        code = form.cleaned_data["code"]
        valid = verify_totp(user, code) or consume_recovery_code(user, code)
        if not valid:
            cache.set(key, attempts + 1, 300)
            form.add_error("code", "Codigo invalido.")
        else:
            cache.delete(key)
            redirect_to = request.session.pop("pending_2fa_next", reverse("home"))
            request.session.pop("pending_2fa_user", None)
            login(request, user)
            messages.success(request, "Autenticacao em dois fatores confirmada.")
            return redirect(redirect_to)

    return render(request, "registro/login_2fa.html", {"form": form})


@login_required
def cadastro(request):
    if request.user.is_client():
        messages.error(request, "Sem permissao para essa pagina.")
        return redirect("home")

    FormClass = FormUserADM if request.user.is_admin() else ClienteForm
    form = FormClass(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, f"Usuario '{user.username}' cadastrado.")
        return redirect("cadastro")
    return render(request, "registro/cadastro.html", {"form": form})


@login_required
def user_profile(request):
    form = FotoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and "alterar_foto" in request.POST and form.is_valid():
        request.user.foto_perfil = imagem_para_base64(form.cleaned_data["arquivo"])
        request.user.save(update_fields=["foto_perfil"])
        messages.success(request, "Foto atualizada.")
        return redirect("user")
    return render(request, "user/user.html", {"form": form})
