# Política de Acesso — Spec 003 Prescrição e Farmácia

## Princípio

Prescrição e dispensação usam **RBAC + ABAC deny-by-default**. Ser usuário interno (`FUNC`) ou administrador técnico não concede, por si só, capacidade clínica de prescrever, validar ou dispensar.

A ação só é autorizada quando todas as condições aplicáveis são verdadeiras:

1. sessão autenticada e usuário interno ativo;
2. capacidade Django específica;
3. escopo PEP válido para o paciente quando houver dado clínico identificável;
4. estado do `Encounter`/prescrição/lote compatível;
5. regra de objeto (autoria, estoque, etc.) quando aplicável.

## Capacidades Django previstas

| Codename | Finalidade |
|---|---|
| `prescription.view_medication_request` | listar/visualizar prescrições no próprio escopo PEP |
| `prescription.prescribe_medication` | criar/submeter prescrição |
| `prescription.validate_medication_request` | realizar validação farmacêutica |
| `prescription.cancel_medication_request` | cancelar prescrição conforme estado/política |
| `prescription.view_medication_dispense` | visualizar dispensações no próprio escopo PEP |
| `prescription.dispense_medication` | confirmar dispensação e consumo de lote |
| `prescription.view_drug` | consultar catálogo interno |
| `prescription.manage_drug_catalog` | manter catálogo e referências aprovadas |
| `prescription.view_pharmacy_stock` | consultar estoque farmacêutico |
| `prescription.manage_pharmacy_stock` | entrada/ajuste controlado de estoque |

Grupos Django podem agrupar essas permissões em perfis institucionais (por exemplo, prescritor/farmacêutico), mas o código testa capacidades, não nomes hardcoded de grupo.

## Papel base

- usuário anônimo: nenhum acesso;
- `CLI`: nenhum acesso ao módulo;
- `FUNC`: nenhum privilégio farmacêutico automático; recebe somente capacidades atribuídas por grupo/permissão;
- `ADM`: mantém o escopo PEP global já existente, mas **ações clínicas críticas continuam exigindo capacidade explícita** (`prescribe`, `validate`, `dispense`). Administração técnica não equivale a habilitação profissional.

## ABAC por paciente/encontro

Para prescrição/validação/dispensação identificável:

- `can_access_patient(user, patient)` do PEP precisa ser verdadeiro;
- o `Encounter` deve pertencer ao mesmo paciente e estar no estado exigido pela operação;
- querysets e choices de formulário são filtrados no servidor; ocultar opção no template nunca é a única barreira;
- objeto fora do escopo clínico deve preferir 404 quando revelar sua existência puder expor PHI.

## Regras por operação

### Visualizar prescrição

Requer:

```text
view_medication_request
AND can_access_patient(patient)
```

### Criar/submeter

Requer:

```text
prescribe_medication
AND can_access_patient(patient)
AND encounter.status == OPEN
```

A submissão deve respeitar autoria ou outra política explicitamente aprovada; não permitir que um usuário sem capacidade modifique DRAFT de outro usuário apenas por conhecer UUID.

### Validar

Requer:

```text
validate_medication_request
AND can_access_patient(patient)
AND request.status == SUBMITTED
```

Esta spec **não presume** regra institucional de proibição de auto-validação. Caso a governança exija separação prescritor ≠ validador, a regra deve ser aprovada e adicionada ao contrato/testes antes de codificar.

### Cancelar

- DRAFT pode ser descartada/cancelada pelo autor autorizado sem apagar histórico persistido relevante;
- SUBMITTED/VALIDATED usa `cancel_medication_request` + escopo PEP + motivo;
- prescrição com dispensação não dispara estorno automático de estoque;
- qualquer devolução exige fluxo posterior explícito.

### Dispensar

Requer:

```text
dispense_medication
AND can_access_patient(patient)
AND request.status == VALIDATED
AND lot/stock elegível
```

A permissão clínica não substitui locking/constraint de estoque.

### Catálogo e referência

- leitura: `view_drug`;
- manutenção: `manage_drug_catalog`;
- ativar `Interaction`/`DoseRule` exige que a referência esteja completa e aprovada;
- usuário com acesso ao catálogo não recebe acesso a prescrições de pacientes.

### Estoque

- consulta: `view_pharmacy_stock`;
- ajuste/entrada: `manage_pharmacy_stock`;
- usuário de estoque sem escopo PEP pode consultar saldos agregados e lotes, mas não recebe nomes de pacientes/prescrições;
- detalhes de `MedicationDispense` continuam exigindo escopo PEP.

## Minimização de PHI

Nunca incluir em logs/eventos técnicos:

- nome/CPF/data de nascimento;
- instrução da prescrição;
- alergia;
- justificativa clínica textual;
- motivo de cancelamento livre;
- conteúdo de evolução.

IDs UUID técnicos são permitidos somente quando necessários para rastreabilidade interna.

## Interface e enumerações

- selects/autocomplete de encontro mostram apenas objetos já autorizados;
- endpoints HTMX/fetch internos reaplicam a mesma política;
- uma resposta 403/404 não deve incluir label de medicamento/paciente pertencente a objeto não autorizado;
- CSRF obrigatório em mutações.

## Auditoria

- leitura de prescrição/dispensação identificável gera evento de acesso quando aplicável;
- criação, submissão, validação, cancelamento, dispensação e ajuste de estoque são auditados;
- auditoria registra ator/objeto/ação/timestamp e metadados técnicos mínimos;
- `django-auditlog` deve excluir campos textuais sensíveis definidos no data model.

## Matriz mínima de testes

| Caso | Esperado |
|---|---|
| anônimo em `/prescricoes/` | redirect login |
| `CLI` autenticado | deny |
| `FUNC` sem capacidade | deny |
| usuário com capacidade mas sem PEP | 404/nenhum PHI |
| prescritor com PEP + encontro aberto | criar/submeter permitido |
| validador com PEP + SUBMITTED | validar se safety gates permitirem |
| dispensador com PEP + VALIDATED + lote elegível | dispensar permitido |
| estoque sem PEP | ver saldo agregado, não dispensação identificável |
| UUID de prescrição fora do escopo | 404 sem conteúdo clínico |
| permissão revogada entre GET e POST | POST negado após revalidação |
