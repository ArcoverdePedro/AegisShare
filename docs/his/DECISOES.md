# Decisões externas do HIS

Registro dos gates do plano (`docs/AEGISSHARE_PLANO_EXECUCAO_IA.md`, seção 04). Nenhuma aprovação humana foi registrada até agora; "Pendente" significa que o código só pode avançar na parte técnica reversível, com a ativação desligada.

| ID | Pergunta | Responsável | Alternativas | Impacto | Decisão | Data/versão | Evidência |
| --- | --- | --- | --- | --- | --- | --- | --- |
| G01 | Serviços, unidades, perfis, nº de instituições, trilhas de faturamento | Direção/produto e operação | (a) hospital geral único, particular+convênio; (b) + SUS; (c) várias instituições na mesma instância | Escopo de H01–H35; (c) exige isolamento por tenant antes de compartilhar dados (H02) | Pendente. Provisório para desenvolvimento sintético: hospital geral único, recepção/ambulatório, urgência, internação, prescrição/farmácia, enfermagem, diagnóstico, materiais, compras, faturamento particular/convênio; SUS em aberto | — | — |
| G02 | Identificação, desconhecidos, duplicidades, responsáveis, acesso emergencial; matriz papel → capacidades | Cadastro, assistência, privacidade | identidade provisória com regularização; conciliação manual com auditoria; matriz proposta em `sync_role_groups` (simulação por padrão) | H02/H03 | Pendente — proposta técnica pronta para revisão, nenhum grupo aplicado | — | `python manage.py sync_role_groups` |
| G03 | Terminologia/estados de alergia e elegibilidade para checagem | Clínico e farmácia | ver `specs/001-pep/extensions/allergy-intolerance/` (T-ALLERGY-02..05) | H05/H07 | Pendente | — | — |
| G04 | Fonte/licença de Interaction/DoseRule; peso elegível | Governança clínica/farmacêutica | T-RX-02, T-NUR-09 | H07/H08 | Pendente | — | — |
| G05 | Documentos assináveis, padrão, credenciais, guarda | Jurídico, clínico, técnico | ICP-Brasil (PAdES/CAdES) vs. assinatura avançada; T-PEP-08 | H06 | Pendente | — | — |
| G06 | Aprazamento, exceções de medicação, cuidados, triagem, alertas | Enfermagem, medicina, farmácia | T-NUR-11; protocolo de triagem institucional | H08–H12 | Pendente | — | — |
| G07 | Catálogos, críticos, laudos, equipamentos de diagnóstico | Laboratório e imagem | — | H14–H16 | Pendente | — | — |
| G08 | Regras cirúrgicas, anestesia, checklists, consentimentos | Centro cirúrgico | — | H17/H18 | Pendente | — | — |
| G09 | Unidades/conversões, autorizações, tabelas, impostos, momento da cobrança | Suprimentos, financeiro, contratos | — | H19–H25 | Pendente | — | — |
| G10 | Retenção, bases legais, titulares, fornecedores, incidentes | Controlador/encarregado, jurídico | — | H28 | Pendente | — | — |
| G11 | Infraestrutura, credenciais, parceiros, restauração, metas | Operação | armazenamento: `local` (volume privado) ou Pinata — ambos suportados desde H29 | H27/H30 | Pendente (escolha de backend e RPO/RTO) | — | — |

Gates herdados das specs, conferidos em 26/10/2026 no commit 38c6100: T-PEP-08, T-RX-02, T-RX-17, T-NUR-09, T-NUR-11 continuam BLOCKED em `specs/*/tasks.md`; T-ALLERGY-02..05 continuam abertos em `specs/001-pep/extensions/allergy-intolerance/tasks.md`.
