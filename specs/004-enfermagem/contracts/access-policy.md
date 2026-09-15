# Contrato — Acesso e Autorização da Enfermagem

## Princípio

Acesso de Enfermagem é **deny-by-default**. Permissão Django representa capacidade funcional; ela nunca substitui o escopo clínico do PEP.

## Capacidades propostas

```text
nursing.view_nursing
nursing.record_vitals
nursing.administer_medication
```

Não criar grupos/roles adicionais apenas por conveniência se as permissões existentes puderem ser atribuídas aos grupos institucionais já usados pelo projeto.

## Regras de acesso

1. Usuário deve estar autenticado.
2. A rota exige a capacidade correspondente.
3. O `Encounter` deve estar dentro de `accessible_patients(user)`/mecanismo PEP equivalente aprovado.
4. Se contexto ADT/local for aplicado à instituição, ele pode restringir adicionalmente o acesso; nunca amplia escopo PEP.
5. Objetos fora do escopo devem preferir 404 quando confirmar sua existência puder revelar PHI.
6. Papel de cliente/usuário não assistencial continua sem acesso clínico mesmo que receba uma permissão incompatível por configuração acidental, conforme boundaries de segurança do PEP.
7. Toda mutação revalida autorização no momento do POST; não confiar em estado carregado anteriormente no navegador.
8. Sincronização offline revalida sessão, capacidade, escopo PEP e estado do encontro no servidor.

## Matriz mínima

| Operação | Capacidade | Escopo PEP | Encontro aberto | Rede |
|---|---|---:|---:|---:|
| Ver histórico de enfermagem | `view_nursing` | obrigatório | não necessariamente | online |
| Registrar sinais vitais | `record_vitals` | obrigatório | obrigatório | online ou piloto offline aprovado |
| Corrigir sinais vitais | `record_vitals` | obrigatório | obrigatório | online; offline só se contrato permitir explicitamente |
| Ver medicações para administrar | `administer_medication` | obrigatório | obrigatório | online |
| Confirmar administração | `administer_medication` | obrigatório | obrigatório | online obrigatório |

## Auditoria de acesso

Leituras identificáveis relevantes devem emitir o mesmo evento/auditoria `ACCESS` usado pelo PEP, com IDs técnicos e sem copiar valores dos sinais vitais ou detalhes de medicamento para logs técnicos.

## Respostas seguras

- sem autenticação: fluxo normal de login;
- sem capacidade: 403 quando isso não revelar existência clínica indevida;
- objeto fora do escopo: 404 preferencial;
- encontro inválido/fechado em mutação: conflito/erro de domínio seguro;
- nenhuma resposta de negação inclui nome do paciente, medicamento, dose ou valores clínicos.
