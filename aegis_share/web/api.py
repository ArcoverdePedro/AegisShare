import logging
from functools import wraps
from io import BytesIO

from auditlog.signals import accessed
from django.http import FileResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from aegis_share.file_policy import FilePolicyError
from aegis_share.models import CustomUser
from aegis_share.services.antivirus import AntivirusError
from aegis_share.services.files import create_file_from_upload, get_version_content
from aegis_share.services.pinata import PinataError
from aegis_share.services.security import authenticate_api_token
from aegis_share.services.selectors import files_for_user, get_accessible_file

logger = logging.getLogger(__name__)


def api_auth(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return JsonResponse({"error": "unauthorized"}, status=401)
        user = authenticate_api_token(auth.removeprefix("Bearer ").strip())
        if not user:
            return JsonResponse({"error": "invalid_token"}, status=401)
        request.api_user = user
        return view(request, *args, **kwargs)

    return wrapped


def _serialize_file(file):
    current_version = file.current_version
    return {
        "id": file.id,
        "name": file.nome_arquivo,
        "mime_type": file.mime_type,
        "size": file.tamanho_arquivo,
        "sha256": file.sha256,
        "encrypted": file.is_encrypted,
        "owner": str(file.dono_arquivo_id),
        "created_at": file.data_adicionado.isoformat(),
        "version": current_version.version_number if current_version else None,
    }


@csrf_exempt
@api_auth
@require_http_methods(["GET", "POST"])
def files_api(request):
    user = request.api_user
    if request.method == "GET":
        qs = files_for_user(user)
        query = request.GET.get("q", "").strip()
        if query:
            qs = qs.filter(nome_arquivo__icontains=query)
        return JsonResponse({"results": [_serialize_file(file) for file in qs[:200]]})

    uploaded = request.FILES.get("file")
    if not uploaded:
        return JsonResponse({"error": "file_required"}, status=400)

    if user.is_client():
        owner = user
    else:
        owner_id = request.POST.get("owner_id", "").strip()
        if not owner_id:
            return JsonResponse({"error": "owner_required"}, status=400)
        owner = CustomUser.objects.filter(
            id=owner_id,
            nivel_permissao="CLI",
            is_active=True,
        ).first()
        if not owner:
            return JsonResponse({"error": "invalid_owner"}, status=400)

    try:
        file = create_file_from_upload(
            uploaded_file=uploaded,
            owner=owner,
            actor=user,
            description=request.POST.get("description", ""),
        )
    except FilePolicyError:
        return JsonResponse(
            {
                "error": "invalid_file",
                "detail": "O arquivo nao atende a politica de upload do servidor.",
            },
            status=400,
        )
    except AntivirusError:
        return JsonResponse({"error": "file_rejected"}, status=400)
    except PinataError:
        logger.warning("api_upload_storage_unavailable", exc_info=True)
        return JsonResponse({"error": "storage_unavailable"}, status=503)
    except Exception:
        logger.exception("api_upload_failed")
        return JsonResponse({"error": "upload_failed"}, status=500)

    return JsonResponse(_serialize_file(file), status=201)


@csrf_exempt
@api_auth
@require_http_methods(["GET"])
def file_api(request, file_id):
    file = get_accessible_file(request.api_user, file_id)
    if not file:
        return JsonResponse({"error": "not_found"}, status=404)
    accessed.send(file.__class__, instance=file)
    data = _serialize_file(file)
    data["versions"] = [
        {
            "id": str(version.id),
            "number": version.version_number,
            "sha256": version.sha256,
            "created_at": version.created_at.isoformat(),
        }
        for version in file.versions.all()
    ]
    return JsonResponse(data)


@csrf_exempt
@api_auth
@require_http_methods(["GET"])
def file_download_api(request, file_id):
    file = get_accessible_file(request.api_user, file_id)
    if not file or not file.current_version:
        return JsonResponse({"error": "not_found"}, status=404)
    accessed.send(file.__class__, instance=file)
    content = get_version_content(file.current_version)
    response = FileResponse(
        BytesIO(content),
        as_attachment=True,
        filename=file.nome_arquivo,
        content_type=file.mime_type or "application/octet-stream",
    )
    response["Cache-Control"] = "private, no-store"
    return response
