# Contrato HTMX — Spec 002 ADT

## Mapa de leitos

| Gatilho | Rota | Template parcial | Alvo | Observação |
|---|---|---|---|---|
| carregamento inicial | `GET /leitos/mapa/` | `clinical/adt/_bed_map.html` | `#bed-map` | renderização autorizada no servidor |
| `every 5s` como fallback | `GET /leitos/mapa/` | `clinical/adt/_bed_map.html` | `#bed-map` | polling pode ser desligado quando socket saudável |
| evento WebSocket `bed-map.changed` | `GET /leitos/mapa/` | `clinical/adt/_bed_map.html` | `#bed-map` | socket sinaliza apenas invalidação |
| filtro por unidade | `GET /leitos/mapa/?location=<uuid>` | `clinical/adt/_bed_map.html` | `#bed-map` | parâmetros validados por selector |

## Regras de segurança

- o fragmento é sempre renderizado após nova verificação de sessão/RBAC/ABAC;
- o WebSocket nunca envia HTML, nome de paciente, CPF, diagnóstico ou motivo de internação;
- usuários autorizados apenas ao mapa operacional veem status do leito sem identificação do ocupante;
- usuários com grant PEP válido podem receber o mínimo identificável necessário definido pela view, nunca conteúdo clínico;
- o partial não deve ser cacheado pelo service worker;
- respostas devem usar `Cache-Control: no-store` quando contiverem ocupação ou identificação de paciente.

## Feedback de mutação

POSTs de admissão, transferência, bloqueio/desbloqueio e alta podem responder com redirect normal ou fragmento de erro de formulário. Nenhum fluxo usa HTMX para contornar CSRF ou substituir a validação transacional no backend.

Em conflito de ocupação, a interface deve:

1. manter os dados não sensíveis já preenchidos;
2. informar que a disponibilidade mudou;
3. atualizar o mapa/lista de leitos;
4. exigir nova confirmação do usuário para outro destino;
5. nunca escolher outro leito automaticamente.

## Acessibilidade

- `#bed-map` deve ter região anunciável com atualização moderada (`aria-live="polite"` somente para resumo/status, não para cada card);
- mudanças em segundo plano não devem mover foco;
- status não pode depender apenas de cor;
- filtro e ações devem ser operáveis por teclado;
- erros de conflito devem ser anunciados e associados ao formulário correspondente.
