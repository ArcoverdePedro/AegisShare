from django.contrib.auth import views as auth_views
from django.urls import path

from .web import api, auth, chat, dashboard, files, health, security

urlpatterns = [
    path("setup/", auth.FirstSuperuserCreateView.as_view(), name="primeiro_cadastro"),
    path("", dashboard.home, name="home"),
    path("dashboard/", dashboard.dashboard, name="dashboard"),
    path("sobre/", dashboard.sobre, name="sobre"),
    path("login/", auth.custom_login, name="login"),
    path("login/2fa/", auth.login_2fa, name="login_2fa"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("cadastro/", auth.cadastro, name="cadastro"),
    path("user/", auth.user_profile, name="user"),

    path("arquivos/", files.arquivos, name="arquivos"),
    path("arquivos/buscar/", files.buscar_arquivo, name="buscar_arquivo"),
    path("upload/", files.upload, name="upload"),
    path("buscar-cliente/", files.buscar_cliente, name="buscar_cliente"),
    path("buscar-funcionario/", files.buscar_funcionario, name="buscar_funcionario"),
    path("arquivos/<int:file_id>/", files.file_detail, name="file_detail"),
    path("arquivos/<int:file_id>/preview/", files.file_preview, name="file_preview"),
    path("arquivos/<int:file_id>/download/", files.file_download, name="file_download"),
    path("arquivos/<int:file_id>/versoes/<uuid:version_id>/preview/", files.file_preview, name="file_version_preview"),
    path("arquivos/<int:file_id>/versoes/<uuid:version_id>/download/", files.file_download, name="file_version_download"),
    path("arquivos/<int:file_id>/versoes/nova/", files.add_file_version, name="add_file_version"),
    path("arquivos/<int:file_id>/tags/", files.update_file_tags, name="update_file_tags"),
    path("arquivos/<int:file_id>/acessos/novo/", files.share_file_access, name="share_file_access"),
    path("arquivos/<int:file_id>/acessos/<uuid:user_id>/revogar/", files.revoke_file_access, name="revoke_file_access"),
    path("arquivos/<int:file_id>/links/novo/", files.create_file_link, name="create_file_link"),
    path("links/<uuid:link_id>/revogar/", files.revoke_file_link, name="revoke_file_link"),
    path("arquivos/<int:file_id>/comentarios/", files.add_file_comment, name="add_file_comment"),
    path("arquivos/<int:file_id>/excluir/", files.delete_file, name="delete_file"),
    path("lixeira/", files.trash, name="trash"),
    path("lixeira/<int:file_id>/restaurar/", files.restore_file, name="restore_file"),

    path("s/<str:token>/", files.shared_link, name="shared_link"),
    path("s/<str:token>/preview/", files.shared_link_preview, name="shared_link_preview"),
    path("s/<str:token>/download/", files.shared_link_download, name="shared_link_download"),

    path("workspaces/", files.workspaces, name="workspaces"),
    path("solicitacoes/", files.document_requests, name="document_requests"),
    path("solicitacoes/item/<int:item_id>/enviar/", files.fulfill_request_item, name="fulfill_request_item"),
    path("notificacoes/", files.notifications, name="notifications"),
    path("notificacoes/lidas/", files.mark_notifications_read, name="mark_notifications_read"),

    path("chat/", chat.chat_index, name="chat_index"),
    path("chat/users/", chat.user_list, name="user_list"),
    path("chat/conversation/<uuid:user_id>/", chat.get_or_create_conversation, name="get_conversation"),
    path("chat/<uuid:conversation_id>/", chat.load_conversation, name="load_conversation"),

    path("seguranca/", security.security_settings, name="security_settings"),
    path("seguranca/2fa/iniciar/", security.begin_2fa, name="begin_2fa"),
    path("seguranca/2fa/ativar/", security.enable_2fa, name="enable_2fa"),
    path("seguranca/2fa/desativar/", security.disable_2fa, name="disable_2fa"),
    path("seguranca/sessoes/<int:session_id>/revogar/", security.revoke_session, name="revoke_session"),
    path("seguranca/sessoes/revogar-outras/", security.revoke_other_sessions, name="revoke_other_sessions"),
    path("seguranca/tokens/novo/", security.create_token, name="create_api_token"),
    path("seguranca/tokens/<uuid:token_id>/revogar/", security.revoke_token, name="revoke_api_token"),

    path("health/live/", health.live, name="health_live"),
    path("health/ready/", health.ready, name="health_ready"),
    path("health/services/", health.services, name="health_services"),

    path("api/v1/files/", api.files_api, name="api_files"),
    path("api/v1/files/<int:file_id>/", api.file_api, name="api_file"),
    path("api/v1/files/<int:file_id>/download/", api.file_download_api, name="api_file_download"),
]
