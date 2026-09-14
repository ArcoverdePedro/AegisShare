# Contrato de Formulários — Spec 002 ADT

## AdmissionForm

Campos expostos:

- `encounter` — somente encontros `INPATIENT` abertos, sem `Admission` existente e dentro do escopo do usuário;
- `bed` — somente leitos ativos, operacionalmente disponíveis e visíveis ao usuário;
- `admitted_at` — padrão horário atual, não anterior ao início do encontro;
- `operation_key` — hidden UUID opaco gerado pelo servidor.

Validações:

- o paciente/encontro precisa continuar acessível no momento do POST;
- o encontro precisa continuar aberto e do tipo internação;
- o leito precisa continuar disponível dentro da transação;
- `operation_key` repetida retorna o mesmo resultado lógico ou erro idempotente seguro, sem duplicar admissão/ocupação.

## TransferForm

Campos expostos:

- `admission` — apenas admissões ativas no escopo;
- `destination_bed` — leitos disponíveis distintos do atual;
- `transferred_at` — padrão horário atual;
- `reason` — texto curto, opcional/obrigatório conforme decisão operacional antes da implementação;
- `operation_key` — hidden UUID opaco.

Validações:

- deve existir ocupação ativa da admissão;
- destino não pode ser o leito atual;
- destino deve permanecer disponível no commit;
- horário não pode anteceder o início da ocupação atual;
- motivo, se coletado, é sensível e não entra em eventos/logs técnicos.

## DischargeForm

Campos expostos:

- `admission` — somente admissão ativa sem alta;
- `discharged_at` — padrão horário atual;
- `disposition` — `HOME`, `TRANSFER_EXTERNAL`, `DEATH`, `OTHER`;
- `reason` — opcional e sensível;
- `operation_key` — hidden UUID opaco.

Validações:

- admissão ainda ativa;
- encontro ainda aberto;
- `discharged_at` não anterior à admissão/ocupação atual;
- operação fecha `Encounter` e ocupação no serviço transacional, nunca somente no form.

## BedStatusForm

Campos expostos:

- nenhum campo de paciente;
- `operation_key` hidden;
- motivo administrativo de bloqueio somente se aprovado na implementação.

Regras:

- leito ocupado não pode ser bloqueado/desbloqueado por atalho que gere estado impossível;
- `OUT_OF_SERVICE` e fluxos de manutenção avançados permanecem fora do primeiro incremento se não houver contrato específico.

## Renderização e acessibilidade

- campos server-rendered com `<label>` associado;
- erros por campo + erro não-campo visíveis;
- foco deve ir para o primeiro erro após POST inválido;
- controles críticos possuem nome textual, não apenas cor/ícone;
- botões de confirmar transferência/alta devem explicitar a ação;
- não usar autocomplete de navegador em campos que possam carregar PHI sem revisão específica;
- formulários preservam CSRF, sessão e autorização Django.
