# Spec 001 — PEP: Prontuário Eletrônico do Paciente

## Contexto

O PEP é o primeiro bounded context clínico do AegisShare HIS. Deve oferecer cadastro e consulta longitudinal do paciente, encontros assistenciais, evoluções, condições, alergias, observações, prescrições relacionadas e documentos clínicos, preservando auditoria, consentimento e controle de acesso.

## User Stories

- Como profissional assistencial autorizado, quero localizar um paciente e consultar seu prontuário longitudinal.
- Como médico, quero registrar e assinar uma evolução vinculada a um encontro.
- Como profissional autorizado, quero registrar observações, condições e alergias com rastreabilidade.
- Como encarregado de privacidade/auditoria, quero saber quem acessou ou alterou informações clínicas.

## Requisitos Funcionais

- **RF-PEP-01** Cadastrar paciente com identificadores e dados demográficos mínimos.
- **RF-PEP-02** Listar e pesquisar pacientes conforme escopo de acesso.
- **RF-PEP-03** Exibir prontuário longitudinal com encontros, evoluções, observações, alergias, condições e documentos.
- **RF-PEP-04** Criar e consultar encontros clínicos.
- **RF-PEP-05** Registrar evolução clínica vinculada ao profissional e ao encontro.
- **RF-PEP-06** Assinar documentos/evoluções por mecanismo aprovado, mantendo versão imutável do conteúdo assinado.
- **RF-PEP-07** Registrar auditoria de leitura e escrita de dados clínicos sensíveis.
- **RF-PEP-08** Respeitar consentimento, papel profissional e contexto assistencial na autorização.
- **RF-PEP-09** Notificar equipe assistencial de eventos clínicos internos relevantes via WebSocket, sem expor API REST pública.

## Requisitos Não Funcionais

- **RNF-PEP-01** Dados clínicos devem permanecer em PostgreSQL transacional e anexos seguirem a política de armazenamento seguro do Core.
- **RNF-PEP-02** O acesso deve ser negado por padrão quando o vínculo/autorização não puder ser demonstrado.
- **RNF-PEP-03** Alterações em registros assinados devem gerar nova versão/adendo, nunca sobrescrita silenciosa.
- **RNF-PEP-04** Templates devem atender WCAG 2.1 AA e funcionar em desktop/tablet.
- **RNF-PEP-05** O PEP deve interoperar com a Spec 014 sem cachear dados clínicos identificáveis em texto claro.

## Critérios de Aceitação

```gherkin
Cenário: Médico registra evolução
  Dado um paciente com encontro aberto
  E um profissional autenticado com papel médico e acesso ao paciente
  Quando acessa a tela de nova evolução e submete conteúdo válido
  Então o sistema salva a evolução vinculada ao encontro e ao profissional
  E registra auditoria
  E disponibiliza a etapa de assinatura
```

```gherkin
Cenário: Usuário sem vínculo tenta abrir prontuário
  Dado um paciente fora do escopo de acesso do usuário
  Quando o usuário solicita a tela do paciente
  Então o sistema nega o acesso
  E não revela dados clínicos no corpo da resposta
```

## Telas e Fluxos

- `clinical/pep/patient_list.html`
- `clinical/pep/patient_form.html`
- `clinical/pep/patient_detail.html`
- `clinical/pep/encounter_detail.html`
- `clinical/pep/evolution_form.html`
- `clinical/pep/document_sign.html`

## Fora de Escopo

- ADT operacional completo de leitos/transferências.
- Dispensação e administração de medicamentos.
- LIS/RIS/PACS.
- Faturamento.

## Dependências

- Spec 000 Core.
- Spec 013 LGPD/compliance para políticas finais.
- Spec 014 PWA para experiência móvel e offline parcial.

## Riscos

- Regras de acesso clínico insuficientes podem causar exposição indevida.
- Definição de assinatura eletrônica/ICP-Brasil exige validação jurídica e operacional antes da implementação definitiva.
- Dados mestres e duplicidade de pacientes exigem política de identificação/mesclagem posterior.

## Rastreabilidade

| Requisito | Rota/View planejada | Template | Teste |
|---|---|---|---|
| RF-PEP-01 | `/pacientes/novo/` | patient_form | view + Gherkin |
| RF-PEP-02 | `/pacientes/` | patient_list | view + E2E |
| RF-PEP-03 | `/pacientes/<id>/` | patient_detail | view + autorização |
| RF-PEP-04 | `/pacientes/<id>/encontros/`, `/encontros/<id>/` | encounter_detail | integration |
| RF-PEP-05 | `/encontros/<id>/evolucoes/nova/` | evolution_form | Gherkin + E2E |
| RF-PEP-06 | `/documentos/<id>/assinar/` | document_sign | unit + integration |
| RF-PEP-07 | todas as rotas clínicas | — | audit test |
