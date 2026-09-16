# Formulários — Spec 013 v1

## DataSubjectRequestForm (ModelForm)

| Campo | Validação |
|---|---|
| patient | ModelChoiceField obrigatório, queryset `accessible_patients(user)` reconstruído em cada GET/POST |
| category | ChoiceField obrigatório, somente categorias do model |
| summary | texto obrigatório após strip, máximo 2000 caracteres |

Patient inexistente, inativo, vínculo expirado/revogado ou fora do escopo: “Selecione um paciente disponível.” Rótulos das opções usam nome e UUID, sem CPF. Não aceitar ator, status ou timestamp fornecidos pelo cliente como fonte de verdade.

Orientação: “Registre somente o resumo necessário para o atendimento. Não inclua senhas, documentos de identidade ou cópias de prontuário.” A conferência de identidade/representação permanece no procedimento institucional; marcar uma caixa na UI não provaria essa conferência.

## RequestTransitionForm (Form)

| Campo | Validação |
|---|---|
| expected_status | ChoiceField hidden obrigatório; comparar com estado persistido sob lock |
| target_status | ChoiceField, limitado ao próximo estado permitido |
| note | texto strip, máximo 2000 caracteres; obrigatório se destino CLOSED |

Nota vazia ao encerrar: “Registre uma nota de atendimento para encerrar a solicitação.” Mensagem de conflito: “Esta solicitação foi atualizada. Consulte o histórico antes de continuar.”

Não aceitar transição direto para CLOSED, reabertura, nota editando evento anterior ou enum desconhecido. O formulário valida formato; a mesma transição é revalidada contra o estado bloqueado no banco.

## RequestFilterForm (Form, GET)

`status` opcional, choices do model. Paginação via Paginator Django. Sem busca por nome, CPF ou texto livre na URL. Campo inválido exibe erro e lista vazia; nunca remove o escopo PEP.
