# Contrato — Sincronização Offline

## Princípio

Offline é uma exceção controlada por requisito clínico. Nenhum formulário autenticado entra em fila offline automaticamente.

## Envelope local mínimo

```text
idempotency_key
operation_type
created_at
user_session_fingerprint
payload_ciphertext
status: pending|syncing|synced|conflict|failed
retry_count
```

## Regras

1. Cada operação recebe `idempotency_key` única.
2. O payload deve conter apenas os campos necessários ao fluxo aprovado.
3. Dados sensíveis persistidos localmente devem estar protegidos; nunca em texto claro.
4. Ao reconectar, o cliente revalida sessão antes de sincronizar.
5. Se a sessão expirou, a operação permanece bloqueada até nova autenticação; não enviar anonimamente.
6. A view Django reaplica autorização e validação completa no servidor.
7. Reenvio com a mesma `idempotency_key` não pode duplicar o registro.
8. Conflitos devem ser auditados. `last-write-wins` só pode ser usado quando a spec do fluxo permitir; caso contrário exige revisão manual.
9. Sucesso confirmado remove ou minimiza o payload local conforme política de retenção.
10. Logout limpa payloads locais da sessão, salvo mecanismo institucional explicitamente aprovado para recuperação segura.

## Fluxos inicialmente elegíveis

Nenhum até aprovação da spec clínica correspondente. O primeiro piloto recomendado é sinais vitais da Spec 004 Enfermagem, após contratos de dados e risco aprovados.

## Fluxos proibidos por padrão

- assinatura clínica;
- exclusão/revogação de consentimento;
- administração de medicamento sem regra clínica específica;
- download de documento;
- alterações administrativas sensíveis.