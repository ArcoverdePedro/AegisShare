# Contratos implementados — solicitações de procedimentos

Namespace surgery, sessão Django; URLs internas via reverse/nome.

| Método | Rota | FBV / nome | Template |
|---|---|---|---|
| GET | /cirurgias/solicitacoes/ | case_list | clinical/surgery/case_list.html |
| GET/POST | /cirurgias/encontros/<uuid:encounter_id>/solicitacoes/nova/ | case_create | clinical/surgery/case_form.html |
| GET | /cirurgias/solicitacoes/<uuid:pk>/ | case_detail | clinical/surgery/case_detail.html |

PEP encounter_detail oferece “Solicitar procedimento” somente com ambas as capacidades e encontro aberto. Menu oferece consulta com view_cases. Servidor sempre revalida; sem segunda lista no encontro. Lista aceita apenas page e pagina 25, usando select_related encounter__patient/requested_by para as relações renderizadas. Sempre mostrar aviso de ausência de agendamento/autorização.

## Form

`SurgicalCaseForm`: procedure ModelChoiceField, label “Procedimento”; operation_key UUIDField hidden com UUID novo por GET. Botão “Registrar solicitação”. GET mostra ativos; POST aceita procedimento existente para reconhecer retry desativado, mas criação nova exige ativo. Campos inválidos: HTML 200 preservando chave. Não aceitar paciente, ator, horário, retrato, diagnóstico ou prioridade fornecidos pelo cliente.

## Respostas e escopo

Sem sessão: redirect login. Profissional/capacidade insuficiente: 403. Encontro/paciente/solicitação fora de accessible_patients: 404. Método inadequado: 405. CSRF obrigatório. Sucesso/retry: 302 ao detalhe. Encontro fechado, catálogo inativo para operação nova ou chave incompatível: 409 genérico, sem identificação conflitante. Banco/auditoria indisponível: 503 sem conteúdo clínico; nenhuma confirmação parcial. Falha de auditoria de leitura impede entrega identificável.

Namespace todo private/no-store, Vary Cookie e nosniff, incluindo respostas anteriores à FBV. Proteger POST e variáveis sensíveis de relatórios de exceção; auditlog não copia retrato/nome de paciente.

## Mutação e concorrência

Em atomic/set_actor: bloquear encontro, revalidar capacidades e escopo PEP, exigir OPEN inclusive para retry. Consultar operation_key; igualdade de ator/encontro/UUID de procedimento retorna original com ACCESS. Incompatível: 409. Para novo registro, bloquear procedimento, exigir ativo e copiar retrato do banco; CREATE/auditoria na mesma transação.

Lock de encontro serializa retry equivalente. Constraint global protege colisão entre encontros. Recuperar apenas violação identificada dessa unicidade, fora do savepoint que falhou, revalidando equivalência/escopo. Outras falhas de integridade/auditoria não são convertidas em sucesso. Chave nova não é duplicata semântica; nenhum dedup por nome/paciente/procedimento. Nenhuma chamada remota ou evento na transação.

## PWA e retirada

/cirurgias/ network-only seguindo o service worker existente; offline não confirma nem enfileira. Não persistir conteúdo em Cache Storage/IndexedDB/localStorage/sessionStorage. Metadata de navegação existente não inclui dados clínicos.

Piloto sintético com atribuição explícita de catálogo/capacidades. Retirada revoga capacidades/desativa catálogo e preserva solicitações/auditoria. Rollback de código preserva dados; reversão do schema apenas em banco descartável, pois elimina evidências.
