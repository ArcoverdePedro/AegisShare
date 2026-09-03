from datetime import datetime, timedelta
from io import BytesIO

from auditlog.signals import accessed
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from aegis_share.forms import (
    DocumentRequestForm,
    FileCommentForm,
    FolderForm,
    IPFSForm,
    SharedLinkForm,
    VersionUploadForm,
    WorkspaceForm,
)
from aegis_share.models import (
    CustomUser,
    DocumentRequest,
    DocumentRequestItem,
    FileComment,
    FileVersion,
    Folder,
    Notification,
    SharedLink,
    Workspace,
    WorkspaceMember,
)
from aegis_share.services.files import (
    create_file_from_upload,
    create_new_version,
    get_version_content,
    grant_access,
    revoke_access,
)
from aegis_share.services.notifications import notify, notify_document_request
from aegis_share.services.selectors import files_for_user, get_accessible_file
from aegis_share.services.sharing import (
    SharedLinkError,
    consume_download,
    create_shared_link,
    resolve_shared_link,
    revoke_shared_link,
)


def _apply_file_filters(queryset, request):
    name = request.GET.get("nome", "").strip()
    owner = request.GET.get("dono", "").strip()
    date_min = request.GET.get("data_min", "").strip()
    date_max = request.GET.get("data_max", "").strip()
    ordering = request.GET.get("ordenar", "")
    mime = request.GET.get("tipo", "").strip()
    tag = request.GET.get("tag", "").strip()
    scope = request.GET.get("escopo", "").strip()

    if name:
        queryset = queryset.filter(nome_arquivo__icontains=name)
    if owner:
        queryset = queryset.filter(dono_arquivo__username__icontains=owner)
    if mime:
        queryset = queryset.filter(mime_type__icontains=mime)
    if tag:
        queryset = queryset.filter(tags__name__icontains=tag)
    if scope == "meus":
        queryset = queryset.filter(dono_arquivo=request.user)
    elif scope == "compartilhados":
        queryset = queryset.filter(usuarios_permitidos=request.user).exclude(dono_arquivo=request.user)

    for value, lookup in ((date_min, "data_adicionado__date__gte"), (date_max, "data_adicionado__date__lte")):
        if value:
            try:
                parsed = datetime.strptime(value, "%d/%m/%Y").date()
                queryset = queryset.filter(**{lookup: parsed})
            except ValueError:
                pass

    if ordering == "tamanho_menor":
        queryset = queryset.order_by("tamanho_arquivo")
    elif ordering == "tamanho_maior":
        queryset = queryset.order_by("-tamanho_arquivo")
    elif ordering == "nome":
        queryset = queryset.order_by("nome_arquivo")
    return queryset.distinct()


@login_required
def buscar_cliente(request):
    term = request.GET.get("term", "").strip()
    clientes = CustomUser.objects.filter(
        nivel_permissao="CLI", is_active=True, username__icontains=term
    ).order_by("username")[:10]
    return JsonResponse([{"id": str(c.id), "nome": c.username} for c in clientes], safe=False)


@login_required
def buscar_funcionario(request):
    term = request.GET.get("term", "").strip()
    users = CustomUser.objects.filter(is_active=True, username__icontains=term).exclude(id=request.user.id)[:10]
    return JsonResponse([{"id": str(user.id), "nome": user.username} for user in users], safe=False)


@login_required
def arquivos(request):
    queryset = _apply_file_filters(files_for_user(request.user), request)
    return render(request, "arquivos/arquivos.html", {"arquivos": queryset})


@login_required
def buscar_arquivo(request):
    queryset = _apply_file_filters(files_for_user(request.user), request)
    if request.headers.get("HX-Request"):
        return render(request, "arquivos/htmx_arquivos.html", {"arquivos": queryset})
    return render(request, "arquivos/arquivos.html", {"arquivos": queryset})


@login_required
def upload(request):
    if request.user.is_client():
        messages.error(request, "Clientes enviam arquivos pelas solicitacoes de documentos.")
        return redirect("document_requests")

    form = IPFSForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        owner = get_object_or_404(CustomUser, id=form.cleaned_data["cliente_id"], nivel_permissao="CLI")
        try:
            file = create_file_from_upload(
                uploaded_file=form.cleaned_data["arquivo"],
                owner=owner,
                actor=request.user,
                workspace=form.cleaned_data.get("workspace"),
                folder=form.cleaned_data.get("folder"),
                description=form.cleaned_data.get("description", ""),
            )
        except Exception as exc:
            messages.error(request, f"Nao foi possivel enviar o arquivo: {exc}")
        else:
            messages.success(request, "Arquivo criptografado e enviado com sucesso.")
            return redirect("file_detail", file_id=file.id)
    return render(request, "arquivos/upload.html", {"form": form})


@login_required
def file_detail(request, file_id):
    file = get_accessible_file(request.user, file_id)
    if not file:
        raise Http404
    accessed.send(file.__class__, instance=file)
    return render(
        request,
        "arquivos/file_detail.html",
        {
            "arquivo": file,
            "versions": file.versions.select_related("uploaded_by").all(),
            "comments": file.comments.select_related("user").all(),
            "comment_form": FileCommentForm(),
            "version_form": VersionUploadForm(),
            "shared_link_form": SharedLinkForm(),
            "shared_links": file.shared_links.filter(revoked_at__isnull=True) if file.user_pode_compartilhar(request.user) else [],
        },
    )


def _version_for_file(file, version_id=None):
    if version_id:
        return get_object_or_404(FileVersion, id=version_id, file=file)
    version = file.current_version
    if not version:
        raise Http404("Arquivo sem versao registrada.")
    return version


def _file_response(file, version, *, attachment):
    content = get_version_content(version)
    return FileResponse(
        BytesIO(content),
        as_attachment=attachment,
        filename=file.nome_arquivo,
        content_type=version.mime_type or file.mime_type or "application/octet-stream",
    )


@login_required
def file_preview(request, file_id, version_id=None):
    file = get_accessible_file(request.user, file_id)
    if not file:
        raise Http404
    accessed.send(file.__class__, instance=file)
    return _file_response(file, _version_for_file(file, version_id), attachment=False)


@login_required
def file_download(request, file_id, version_id=None):
    file = get_accessible_file(request.user, file_id)
    if not file:
        raise Http404
    accessed.send(file.__class__, instance=file)
    return _file_response(file, _version_for_file(file, version_id), attachment=True)


@login_required
@require_POST
def add_file_version(request, file_id):
    file = get_accessible_file(request.user, file_id)
    if not file or not file.user_pode_alterar(request.user):
        return HttpResponseForbidden("Sem permissao.")
    form = VersionUploadForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            create_new_version(file=file, uploaded_file=form.cleaned_data["arquivo"], actor=request.user)
            messages.success(request, "Nova versao criada.")
        except Exception as exc:
            messages.error(request, f"Falha ao criar versao: {exc}")
    else:
        messages.error(request, "Arquivo invalido para nova versao.")
    return redirect("file_detail", file_id=file.id)


@login_required
@require_POST
def share_file_access(request, file_id):
    file = get_accessible_file(request.user, file_id)
    if not file:
        raise Http404
    recipient = get_object_or_404(CustomUser, id=request.POST.get("usuario_id"), is_active=True)
    try:
        _, created = grant_access(file=file, recipient=recipient, actor=request.user)
        messages.success(request, "Acesso concedido." if created else "O usuario ja possuia acesso.")
    except PermissionError as exc:
        messages.error(request, str(exc))
    return redirect("file_detail", file_id=file.id)


@login_required
@require_POST
def revoke_file_access(request, file_id, user_id):
    file = get_accessible_file(request.user, file_id)
    if not file:
        raise Http404
    recipient = get_object_or_404(CustomUser, id=user_id)
    try:
        revoke_access(file=file, recipient=recipient, actor=request.user)
        messages.success(request, "Acesso revogado.")
    except PermissionError as exc:
        messages.error(request, str(exc))
    return redirect("file_detail", file_id=file.id)


@login_required
@require_POST
def create_file_link(request, file_id):
    file = get_accessible_file(request.user, file_id)
    if not file:
        raise Http404
    form = SharedLinkForm(request.POST)
    if form.is_valid():
        try:
            link, token = create_shared_link(
                file=file,
                actor=request.user,
                expires_in_hours=form.cleaned_data.get("expires_in_hours") or None,
                password=form.cleaned_data.get("password") or None,
                max_downloads=form.cleaned_data.get("max_downloads"),
                allow_preview=form.cleaned_data.get("allow_preview", False),
                allow_download=form.cleaned_data.get("allow_download", False),
            )
        except PermissionError as exc:
            messages.error(request, str(exc))
        else:
            request.session["new_shared_link"] = request.build_absolute_uri(
                reverse("shared_link", args=[token])
            )
            messages.success(request, "Link criado. Copie-o agora; o token nao fica armazenado em texto puro.")
    else:
        messages.error(request, "Configuracao de link invalida.")
    return redirect("file_detail", file_id=file.id)


@login_required
@require_POST
def revoke_file_link(request, link_id):
    link = get_object_or_404(SharedLink.objects.select_related("file"), id=link_id)
    try:
        revoke_shared_link(link, request.user)
        messages.success(request, "Link revogado.")
    except PermissionError as exc:
        messages.error(request, str(exc))
    return redirect("file_detail", file_id=link.file_id)


def shared_link(request, token):
    password = request.POST.get("password") if request.method == "POST" else None
    try:
        link = resolve_shared_link(token, password=password, for_download=False)
    except SharedLinkError as exc:
        if request.method == "POST":
            return render(request, "arquivos/shared_link.html", {"error": str(exc), "token": token}, status=403)
        # Se possui senha, a primeira abertura deve exibir o formulario sem validar senha vazia.
        candidate = SharedLink.objects.filter(token_hash=__import__("hashlib").sha256(token.encode()).hexdigest()).select_related("file").first()
        if candidate and candidate.is_active and candidate.password_hash:
            return render(request, "arquivos/shared_link.html", {"link": candidate, "token": token, "needs_password": True})
        raise Http404 from exc

    if link.password_hash:
        request.session[f"shared-link-auth:{link.id}"] = True
    link.last_accessed_at = timezone.now()
    link.save(update_fields=["last_accessed_at"])
    return render(request, "arquivos/shared_link.html", {"link": link, "token": token, "authorized": True})


def shared_link_preview(request, token):
    try:
        link = resolve_shared_link(token, for_download=False)
    except SharedLinkError:
        hashed = __import__("hashlib").sha256(token.encode()).hexdigest()
        link = SharedLink.objects.select_related("file").filter(token_hash=hashed).first()
        if not link or not link.is_active or not request.session.get(f"shared-link-auth:{link.id}") or not link.allow_preview:
            raise Http404
    accessed.send(link.file.__class__, instance=link.file)
    return _file_response(link.file, _version_for_file(link.file), attachment=False)


def shared_link_download(request, token):
    try:
        link = resolve_shared_link(token, for_download=True)
        link = consume_download(token)
    except SharedLinkError:
        hashed = __import__("hashlib").sha256(token.encode()).hexdigest()
        candidate = SharedLink.objects.select_related("file").filter(token_hash=hashed).first()
        if not candidate or not request.session.get(f"shared-link-auth:{candidate.id}"):
            raise Http404
        link = consume_download(token, password_verified=True)
    accessed.send(link.file.__class__, instance=link.file)
    return _file_response(link.file, _version_for_file(link.file), attachment=True)


@login_required
@require_POST
def add_file_comment(request, file_id):
    file = get_accessible_file(request.user, file_id)
    if not file:
        raise Http404
    form = FileCommentForm(request.POST)
    if form.is_valid():
        FileComment.objects.create(file=file, user=request.user, content=form.cleaned_data["content"])
        for recipient in {file.dono_arquivo, *file.usuarios_permitidos.all()}:
            if recipient.id != request.user.id:
                notify(
                    recipient,
                    kind="FILE",
                    title=f"Novo comentario em {file.nome_arquivo}",
                    body=form.cleaned_data["content"][:180],
                    link=reverse("file_detail", args=[file.id]),
                )
    return redirect("file_detail", file_id=file.id)


@login_required
@require_POST
def delete_file(request, file_id):
    file = get_accessible_file(request.user, file_id)
    if not file or not file.user_pode_alterar(request.user):
        return HttpResponseForbidden("Sem permissao.")
    file.soft_delete(request.user)
    messages.success(request, "Arquivo movido para a lixeira.")
    return redirect("arquivos")


@login_required
def trash(request):
    files = files_for_user(request.user, include_deleted=True).filter(deleted_at__isnull=False)
    return render(request, "arquivos/trash.html", {"arquivos": files})


@login_required
@require_POST
def restore_file(request, file_id):
    file = get_accessible_file(request.user, file_id, include_deleted=True)
    if not file or not file.user_pode_alterar(request.user):
        return HttpResponseForbidden("Sem permissao.")
    file.restore()
    messages.success(request, "Arquivo restaurado.")
    return redirect("trash")


@login_required
def workspaces(request):
    if request.user.is_admin():
        qs = Workspace.objects.select_related("cliente", "created_by").all()
    else:
        qs = Workspace.objects.filter(Q(cliente=request.user) | Q(members=request.user)).distinct()
    workspace_form = WorkspaceForm(request.POST or None) if not request.user.is_client() else None
    folder_form = FolderForm(request.POST or None) if not request.user.is_client() else None

    if request.method == "POST" and not request.user.is_client():
        if "create_workspace" in request.POST and workspace_form.is_valid():
            workspace = Workspace.objects.create(
                name=workspace_form.cleaned_data["name"],
                cliente=workspace_form.cleaned_data["cliente"],
                created_by=request.user,
            )
            WorkspaceMember.objects.get_or_create(workspace=workspace, user=request.user, defaults={"can_share": True})
            messages.success(request, "Workspace criado.")
            return redirect("workspaces")
        if "create_folder" in request.POST and folder_form.is_valid():
            workspace = folder_form.cleaned_data["workspace"]
            if not workspace.user_has_access(request.user):
                return HttpResponseForbidden("Sem acesso ao workspace.")
            Folder.objects.create(
                workspace=workspace,
                parent=folder_form.cleaned_data.get("parent"),
                name=folder_form.cleaned_data["name"],
                created_by=request.user,
            )
            messages.success(request, "Pasta criada.")
            return redirect("workspaces")

    return render(request, "arquivos/workspaces.html", {"workspaces": qs, "workspace_form": workspace_form, "folder_form": folder_form})


@login_required
def document_requests(request):
    if request.user.is_client():
        qs = DocumentRequest.objects.filter(recipient=request.user).prefetch_related("items")
    else:
        qs = DocumentRequest.objects.filter(Q(created_by=request.user) | Q(recipient=request.user)).prefetch_related("items", "recipient")

    form = None
    if not request.user.is_client():
        form = DocumentRequestForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            with transaction.atomic():
                obj = DocumentRequest.objects.create(
                    title=form.cleaned_data["title"],
                    description=form.cleaned_data.get("description", ""),
                    recipient=form.cleaned_data["recipient"],
                    created_by=request.user,
                    due_at=form.cleaned_data.get("due_at"),
                )
                DocumentRequestItem.objects.bulk_create(
                    [DocumentRequestItem(request=obj, label=label) for label in form.cleaned_data["items"]]
                )
            notify_document_request(obj)
            messages.success(request, "Solicitacao criada.")
            return redirect("document_requests")

    return render(request, "requests/document_requests.html", {"requests": qs, "form": form})


@login_required
@require_POST
def fulfill_request_item(request, item_id):
    item = get_object_or_404(
        DocumentRequestItem.objects.select_related("request", "request__recipient"),
        id=item_id,
        request__recipient=request.user,
    )
    form = VersionUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Arquivo invalido.")
        return redirect("document_requests")

    file = create_file_from_upload(
        uploaded_file=form.cleaned_data["arquivo"],
        owner=request.user,
        actor=request.user,
        description=f"Enviado para solicitacao: {item.request.title} / {item.label}",
    )
    item.fulfilled_by_file = file
    item.completed_at = timezone.now()
    item.save(update_fields=["fulfilled_by_file", "completed_at"])
    item.request.refresh_status()
    notify(
        item.request.created_by,
        kind="REQUEST",
        title=f"Documento recebido: {item.label}",
        body=request.user.username,
        link=reverse("file_detail", args=[file.id]),
    )
    messages.success(request, "Documento enviado e vinculado a solicitacao.")
    return redirect("document_requests")


@login_required
def notifications(request):
    qs = request.user.notifications.all()[:100]
    return render(request, "notifications/list.html", {"notifications": qs})


@login_required
@require_POST
def mark_notifications_read(request):
    request.user.notifications.filter(read_at__isnull=True).update(read_at=timezone.now())
    return redirect(request.POST.get("next") or "notifications")
