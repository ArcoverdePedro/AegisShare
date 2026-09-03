"""Compatibilidade para imports antigos.

Novas rotas importam controllers de ``aegis_share.web`` diretamente.
Este modulo pode ser removido em uma futura major version.
"""

from .web.auth import FirstSuperuserCreateView, cadastro, custom_login, login_2fa, user_profile
from .web.chat import chat_index, get_or_create_conversation, load_conversation, user_list
from .web.dashboard import home, sobre
from .web.files import (
    arquivos,
    buscar_arquivo,
    buscar_cliente,
    buscar_funcionario,
    upload,
)

user = user_profile
