# Contrato de Rotas — Spec 000 Core

| Método | URL | View | Template/Resposta | Permissão |
|---|---|---|---|---|
| GET/POST | `/login/` | `auth.custom_login` | registro/login | público autenticável |
| GET/POST | `/login/2fa/` | `auth.login_2fa` | registro/login_2fa | sessão pré-MFA |
| POST | `/logout/` | Django LogoutView | redirect | autenticado |
| GET | `/dashboard/` | `dashboard.dashboard` | home/dashboard | autenticado |
| GET | `/auditoria/` | `dashboard.audit_log` | audit/list | autorizado |
| GET | `/arquivos/` | `files.arquivos` | arquivos/arquivos | autenticado |
| POST | `/upload/` | `files.upload` | arquivos/upload | autorizado |
| GET | `/arquivos/<id>/` | `files.file_detail` | arquivos/file_detail | acesso ao objeto |
| GET | `/arquivos/<id>/preview/` | `files.file_preview` | stream interno | acesso ao objeto |
| GET | `/arquivos/<id>/download/` | `files.file_download` | download interno | acesso ao objeto |
| POST | `/arquivos/<id>/versoes/nova/` | `files.add_file_version` | redirect/partial | autorizado |
| POST | `/arquivos/<id>/acessos/novo/` | `files.share_file_access` | redirect/partial | proprietário/autorizado |
| POST | `/arquivos/<id>/comentarios/` | `files.add_file_comment` | redirect/partial | acesso ao objeto |
| GET | `/workspaces/` | `files.workspaces` | arquivos/workspaces | autenticado |
| GET/POST | `/solicitacoes/` | `files.document_requests` | requests/document_requests | autenticado |
| GET | `/notificacoes/` | `files.notifications` | notifications/* | autenticado |
| GET | `/chat/` | `chat.chat_index` | chat/chat_index | autenticado |
| GET | `/chat/<conversation_id>/` | `chat.load_conversation` | chat/partials/chat_conversation | participante autorizado |
| GET/POST | `/seguranca/` | `security.security_settings` | security/settings | autenticado |
| GET | `/health/live/` | `health.live` | JSON técnico | infraestrutura |
| GET | `/health/ready/` | `health.ready` | JSON técnico | infraestrutura |

## Rotas legadas incompatíveis com a constituição

As rotas abaixo existem hoje, mas não pertencem ao contrato alvo do HIS e devem ser descontinuadas mediante inventário de consumidores e plano de migração:

- `/api/v1/files/`
- `/api/v1/files/<id>/`
- `/api/v1/files/<id>/download/`

Até a descontinuação, não devem receber novas features.