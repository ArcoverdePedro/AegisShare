from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.sessions.models import Session
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from aegis_share.forms import APITokenForm, TOTPCodeForm
from aegis_share.models import APIToken, TrackedSession, UserSecuritySettings
from aegis_share.services.security import (
    begin_totp_setup,
    create_api_token,
    disable_totp,
    enable_totp,
)


@login_required
def security_settings(request):
    security, _ = UserSecuritySettings.objects.get_or_create(user=request.user)
    context = {
        "security": security,
        "sessions": request.user.tracked_sessions.filter(revoked_at__isnull=True)[:20],
        "api_tokens": request.user.api_tokens.filter(revoked_at__isnull=True)[:20],
        "api_token_form": APITokenForm(),
        "totp_form": TOTPCodeForm(),
        "new_api_token": request.session.pop("new_api_token", None),
        "totp_secret": request.session.pop("totp_secret", None),
        "totp_uri": request.session.pop("totp_uri", None),
        "recovery_codes": request.session.pop("recovery_codes", None),
        "current_session_key": request.session.session_key,
    }
    return render(request, "security/settings.html", context)


@login_required
@require_POST
def begin_2fa(request):
    secret, uri = begin_totp_setup(request.user)
    request.session["totp_secret"] = secret
    request.session["totp_uri"] = uri
    messages.info(request, "Cadastre o segredo no autenticador e confirme um codigo.")
    return redirect("security_settings")


@login_required
@require_POST
def enable_2fa(request):
    form = TOTPCodeForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Codigo invalido.")
        return redirect("security_settings")
    try:
        recovery_codes = enable_totp(request.user, form.cleaned_data["code"])
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        request.session["recovery_codes"] = recovery_codes
        messages.success(request, "2FA ativado. Guarde os codigos de recuperacao em local seguro.")
    return redirect("security_settings")


@login_required
@require_POST
def disable_2fa(request):
    if not request.user.check_password(request.POST.get("password", "")):
        messages.error(request, "Senha atual incorreta.")
        return redirect("security_settings")
    disable_totp(request.user)
    messages.success(request, "2FA desativado.")
    return redirect("security_settings")


@login_required
@require_POST
def revoke_session(request, session_id):
    tracked = get_object_or_404(TrackedSession, id=session_id, user=request.user)
    if tracked.session_key == request.session.session_key:
        messages.error(request, "Use Logout para encerrar a sessao atual.")
        return redirect("security_settings")
    Session.objects.filter(session_key=tracked.session_key).delete()
    tracked.revoked_at = timezone.now()
    tracked.save(update_fields=["revoked_at"])
    messages.success(request, "Sessao encerrada.")
    return redirect("security_settings")


@login_required
@require_POST
def revoke_other_sessions(request):
    current = request.session.session_key
    for tracked in request.user.tracked_sessions.filter(revoked_at__isnull=True).exclude(session_key=current):
        Session.objects.filter(session_key=tracked.session_key).delete()
        tracked.revoked_at = timezone.now()
        tracked.save(update_fields=["revoked_at"])
    messages.success(request, "Outras sessoes encerradas.")
    return redirect("security_settings")


@login_required
@require_POST
def create_token(request):
    form = APITokenForm(request.POST)
    if form.is_valid():
        obj, raw = create_api_token(
            request.user,
            name=form.cleaned_data["name"],
            expires_days=form.cleaned_data.get("expires_days"),
        )
        request.session["new_api_token"] = raw
        messages.success(request, f"Token '{obj.name}' criado. Ele sera exibido apenas uma vez.")
    else:
        messages.error(request, "Dados do token invalidos.")
    return redirect("security_settings")


@login_required
@require_POST
def revoke_token(request, token_id):
    token = get_object_or_404(APIToken, id=token_id, user=request.user)
    token.revoked_at = timezone.now()
    token.save(update_fields=["revoked_at"])
    messages.success(request, "Token revogado.")
    return redirect("security_settings")
