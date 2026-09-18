from io import BytesIO

from django.core.exceptions import (
    PermissionDenied,
    RequestDataTooBig,
    TooManyFieldsSent,
    TooManyFilesSent,
)
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.uploadhandler import FileUploadHandler, StopUpload
from django.http import HttpResponse
from django.http.multipartparser import MultiPartParserError
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.debug import sensitive_variables

from .lab_inbox import MAX_BODY_BYTES, MAX_FILE_BYTES, require_inbox_permission


class LimitedStream:
    """Limita bytes efetivamente lidos, inclusive campos e overhead multipart."""

    def __init__(self, stream):
        self.stream = stream
        self.total = 0

    def _read(self, method, size=-1):
        remaining = MAX_BODY_BYTES - self.total
        data = getattr(self.stream, method)(
            min(size, remaining + 1) if size >= 0 else remaining + 1
        )
        self.total += len(data)
        if self.total > MAX_BODY_BYTES:
            raise RequestDataTooBig
        return data

    def read(self, size=-1):
        return self._read("read", size)

    def readline(self, size=-1):
        return self._read("readline", size)

    def close(self):
        return self.stream.close()


class LaboratoryUploadHandler(FileUploadHandler):
    """Um arquivo em memória, sem fallback para temporários plaintext."""

    def __init__(self, request):
        super().__init__(request)
        self.count = 0
        self.total = 0
        self.rejected = False

    def new_file(self, *args, **kwargs):
        super().new_file(*args, **kwargs)
        self.count += 1
        if self.count > 1:
            self.rejected = True
            raise StopUpload(connection_reset=False)
        self.file = BytesIO()

    def receive_data_chunk(self, raw_data, start):
        self.total += len(raw_data)
        if self.total > MAX_FILE_BYTES:
            self.rejected = True
            self.file.close()
            raise StopUpload(connection_reset=False)
        self.file.write(raw_data)

    def file_complete(self, file_size):
        self.file.seek(0)
        return InMemoryUploadedFile(
            self.file,
            self.field_name,
            "quarantine.bin",
            "application/octet-stream",
            file_size,
            None,
        )

    def upload_interrupted(self):
        if hasattr(self, "file"):
            self.file.close()


class LaboratoryUploadMiddleware:
    """Autoriza e limita multipart antes de CSRF, sem dispensar a verificação CSRF."""

    def __init__(self, get_response):
        self.get_response = get_response

    @sensitive_variables()
    def __call__(self, request):
        if request.method == "POST" and request.path_info == reverse(
            "interoperability:lab_inbox_receive"
        ):
            if not request.user.is_authenticated:
                return redirect("login")
            try:
                require_inbox_permission(request.user, receive=True)
            except PermissionDenied:
                return HttpResponse("Acesso negado.", status=403)
            if request.content_type != "multipart/form-data":
                return HttpResponse("Envie o formulário de recebimento.", status=400)
            handler = LaboratoryUploadHandler(request)
            request.upload_handlers = [handler]
            request._stream = LimitedStream(request._stream)
            try:
                _ = request.POST
                if handler.rejected:
                    return HttpResponse(
                        "Upload excede o limite ou contém múltiplos arquivos.", status=413
                    )
            except RequestDataTooBig, TooManyFieldsSent, TooManyFilesSent:
                return HttpResponse("Upload excede o limite.", status=413)
            except MultiPartParserError:
                return HttpResponse("Upload inválido.", status=400)
        return self.get_response(request)
