import base64
import re
from io import BytesIO

from PIL import Image

from .services.files import grant_access
from .services.selectors import files_for_user


def arquivos_por_permissao(user):
    """Compatibilidade com templates/views antigas; consultas ficam em selectors."""
    return files_for_user(user)


def dar_acesso(arquivo, usuario_alvo, actor=None):
    """Compatibilidade. Novos fluxos devem sempre informar o ator."""
    if actor is None:
        raise ValueError("O ator e obrigatorio para conceder acesso com auditoria.")
    return grant_access(file=arquivo, recipient=usuario_alvo, actor=actor)


def clear_strings(value):
    if not value:
        return ""
    return re.sub(r"[^0-9]", "", value)


def imagem_para_base64(arquivo_imagem):
    img = Image.open(arquivo_imagem).convert("RGB")
    img.thumbnail((512, 512))
    buffer = BytesIO()
    img.save(buffer, format="AVIF", quality=75)
    base64_str = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/avif;base64,{base64_str}"
