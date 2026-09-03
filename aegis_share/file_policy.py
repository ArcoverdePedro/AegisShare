from django.conf import settings

SAFE_FILE_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "text/plain",
    "text/csv",
    "application/zip",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/msword",
    "application/vnd.ms-excel",
    "application/vnd.ms-powerpoint",
    "audio/mpeg",
    "audio/ogg",
    "video/mp4",
    "video/webm",
}


class FilePolicyError(ValueError):
    pass


def validate_file_metadata(*, size: int, content_type: str | None) -> None:
    max_size = settings.FILE_MAX_UPLOAD_MB * 1024 * 1024
    if size <= 0:
        raise FilePolicyError("O arquivo esta vazio.")
    if size > max_size:
        raise FilePolicyError(
            f"O arquivo excede o limite de {settings.FILE_MAX_UPLOAD_MB} MB."
        )
    mime = content_type or "application/octet-stream"
    if mime not in SAFE_FILE_TYPES:
        raise FilePolicyError(
            "Tipo de arquivo nao permitido. Envie documentos, imagens, ZIP, audio ou video suportados."
        )


def validate_uploaded_file(uploaded_file) -> None:
    validate_file_metadata(
        size=getattr(uploaded_file, "size", 0),
        content_type=getattr(uploaded_file, "content_type", None),
    )
