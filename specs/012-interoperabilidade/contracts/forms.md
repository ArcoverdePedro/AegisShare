# Formulários — Spec 012 v1 (v1 aprovada)

`PatientExportForm` usa `forms.Form`, pois representa uma operação, não edição de cadastro.

| Campo | Tipo | Validação/mensagem |
|---|---|---|
| patient | ModelChoiceField obrigatório | queryset `accessible_patients(user)`; inexistente/inativo/fora do escopo: “Selecione um paciente disponível.” |
| confirm | BooleanField obrigatório | “Confirme a exportação dos dados selecionados.” |

Permissão: profissional interno + `interoperability.export_patient`. O queryset é reconstruído no POST; campo oculto, escolha manipulada ou UUID conhecido não conferem autorização. Erros escapados pelo DTL. Não aceitar campos de destino remoto, formato livre ou parâmetros que ampliem a allowlist.

Texto de confirmação: “O arquivo contém nome e data de nascimento. Salve-o somente em local autorizado. Sair do sistema não remove arquivos baixados.” Essa confirmação não é consentimento do paciente nem base legal.
