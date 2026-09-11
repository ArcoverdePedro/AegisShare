# Contrato de Formulários — Spec 000 Core

| Formulário/Fluxo | Campos principais | Validações | Permissão |
|---|---|---|---|
| Login | usuário, senha | credenciais válidas, rate limit, fluxo MFA quando habilitado | público autenticável |
| MFA TOTP | código | TOTP válido e não expirado | sessão pré-MFA |
| Cadastro de usuário | dados de conta e papel | unicidade, política de senha, papel permitido | administrador |
| Upload de documento | arquivo, metadados, proprietário | política de arquivo, tamanho/tipo, autorização | autorizado |
| Nova versão | arquivo | política de arquivo, acesso ao documento | proprietário/autorizado |
| Compartilhamento interno | usuário, permissão | destinatário válido, menor privilégio | proprietário/autorizado |
| Link compartilhável | expiração, senha/opções | prazo, política de acesso, token seguro | proprietário/autorizado |
| Comentário | texto | tamanho, acesso ao documento | usuário com acesso |
| Configuração MFA | segredo/código TOTP | confirmação do código | autenticado |

## Regra transversal

Toda validação de permissão deve ocorrer no backend. O template pode esconder ações indisponíveis, mas isso nunca substitui a verificação na view/serviço.