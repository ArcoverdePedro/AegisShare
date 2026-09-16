# Arquivo Patient — contrato `patient-r4-v1` aprovado

Versão fixa: FHIR **R4 4.0.1**, não negociação automática de versão. O recurso Patient representa dados demográficos; o JSON FHIR usa `resourceType` e os tipos próprios de seus elementos. Referências consultadas em 2026-09-16: [Patient R4](https://hl7.org/fhir/R4/patient.html) e [JSON R4](https://hl7.org/fhir/R4/json.html).

## Allowlist local

| Campo de saída | Origem/regra |
|---|---|
| resourceType | string `Patient` |
| id | string UUID de `Patient.id` |
| active | boolean de `Patient.active` |
| name | array com um objeto contendo apenas `text = full_name` |
| birthDate | `birth_date` no formato `YYYY-MM-DD` |

Todos os demais campos são omitidos. Em particular: identifier/CPF, telefone, e-mail, gender, encontros, medicamentos, observações, narrativa XHTML, extensões e meta.profile. Não dividir nomes em sobrenome/prenome por heurística. Não converter sexo registrado em gênero administrativo. Não acrescentar campos nulos ou strings vazias.

JSON UTF-8, sem BOM, gerado por `json.dumps(..., ensure_ascii=False, allow_nan=False)` e encoding UTF-8. O SHA-256 é calculado após serialização, sobre os mesmos bytes da resposta.

Esta allowlist é um contrato local mínimo, não um perfil FHIR nacional publicado. Não declarar conformidade RNDS nem compatibilidade com sistemas externos sem validação específica. Importação/reconciliação por nome ou data de nascimento não está autorizada.
