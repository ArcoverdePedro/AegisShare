# Contrato — Manifest PWA

## Campos obrigatórios

| Campo | Valor/Regra |
|---|---|
| `name` | `AegisShare HIS` |
| `short_name` | `AegisShare` |
| `description` | Sistema Hospitalar Interno |
| `start_url` | `/` |
| `scope` | `/` |
| `display` | `standalone` |
| `orientation` | `portrait` por padrão, revisável por tela |
| `theme_color` | token institucional aprovado |
| `background_color` | token de superfície compatível com tema |
| ícone 192 | PNG 192x192 |
| ícone 512 | PNG 512x512 |

## Regras

- Manifest não deve conter dados do usuário/hospital que sejam sensíveis por ambiente.
- O aplicativo deve continuar funcional se instalado e o tema do dispositivo mudar.
- Ícones devem ter versão maskable quando possível.
- `start_url` deve exigir autenticação normalmente; instalação não cria sessão especial.
