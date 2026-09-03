"""Compatibilidade temporaria para imports antigos.

Novas rotas importam controllers de ``aegis_share.web`` diretamente.
Este modulo pode ser removido em uma futura major version.
"""

from .web.auth import FirstSuperuserCreateView as FirstSuperuserCreateView
from .web.auth import cadastro as cadastro
from .web.auth import custom_login as custom_login
from .web.auth import login_2fa as login_2fa
from .web.auth import user_profile as user_profile
from .web.chat import chat_index as chat_index
from .web.chat import get_or_create_conversation as get_or_create_conversation
from .web.chat import load_conversation as load_conversation
from .web.chat import user_list as user_list
from .web.dashboard import home as home
from .web.dashboard import sobre as sobre
from .web.files import arquivos as arquivos
from .web.files import buscar_arquivo as buscar_arquivo
from .web.files import buscar_cliente as buscar_cliente
from .web.files import buscar_funcionario as buscar_funcionario
from .web.files import upload as upload

user = user_profile

__all__ = [
    "FirstSuperuserCreateView",
    "arquivos",
    "buscar_arquivo",
    "buscar_cliente",
    "buscar_funcionario",
    "cadastro",
    "chat_index",
    "custom_login",
    "get_or_create_conversation",
    "home",
    "load_conversation",
    "login_2fa",
    "sobre",
    "upload",
    "user",
    "user_list",
    "user_profile",
]
