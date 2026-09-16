import base64
import re
from io import BytesIO

from PIL import Image


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
