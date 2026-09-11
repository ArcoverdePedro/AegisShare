# Inventário e migração da API pública legada

Status: aprovado pela Spec 000 para execução incremental. Este documento cobre T-CORE-01 e T-CORE-03 e **não autoriza a remoção imediata** das rotas.

## Objetivo

Inventariar os consumidores conhecidos de `api/v1/*`, registrar o risco de consumidores externos e definir uma migração reversível para o modelo alvo do Core: views/formulários Django, serviços Python internos, arquivos e jobs internos, sem API REST pública obrigatória.

## Superfície legada existente

| Rota | Método | Responsabilidade atual | Alternativa interna alvo |
|---|---|---|---|
| `/api/v1/files/` | `GET` | listar arquivos acessíveis | `files_for_user()` + view `arquivos`/HTMX |
| `/api/v1/files/` | `POST` | criar upload | `IPFSForm` + `create_file_from_upload()` |
| `/api/v1/files/<id>/` | `GET` | metadados/versões de arquivo | `get_accessible_file()` + `file_detail` |
| `/api/v1/files/<id>/download/` | `GET` | download do conteúdo | `get_accessible_file()` + `get_version_content()`/`file_download` |

Não foram identificadas outras rotas públicas `api/v1/*` no código versionado.

## Consumidores encontrados no repositório

A busca no código versionado encontrou referências às rotas da API em:

- configuração de URLs e implementação da própria API;
- testes da superfície HTTP e teste arquitetural que impede expansão da API pública;
- README, changelog, ADRs e contratos da Spec 000.

**Não foi encontrado consumidor de runtime interno** chamando a API HTTP para implementar uma funcionalidade do próprio monólito. As funcionalidades equivalentes já possuem views, formulários, selectors e serviços Python internos.

Essa conclusão é limitada ao repositório. Ela não prova ausência de integrações de terceiros ou scripts mantidos fora do GitHub.

## Evidência de possível consumo externo

O sistema permite criar tokens Bearer pela tela de Segurança, e `APIToken` registra `last_used_at` quando um token é autenticado. Além disso, o README historicamente publicou os endpoints. Portanto, consumidores externos são tecnicamente possíveis e devem ser tratados como dependência até verificação operacional.

Antes de retirar qualquer rota, a operação deve verificar:

1. tokens ativos e respectivos `last_used_at`;
2. logs do proxy/aplicação para requisições a `/api/v1/` durante um período de observação aprovado pelo mantenedor;
3. integrações, scripts e automações conhecidas fora deste repositório;
4. responsáveis por cada consumidor identificado e sua alternativa de migração.

A ausência de referências no repositório, isoladamente, não é critério suficiente para remover a API em produção.

## Estratégia de migração

### Fase 0 — congelar a expansão

Concluída pelo teste arquitetural da Spec 000: novas rotas públicas `/api/` não devem ser adicionadas.

### Fase 1 — inventariar e observar

Manter as rotas funcionando e coletar evidência operacional. Classificar cada consumidor externo como `ativo`, `inativo`, `desconhecido` ou `migrado`. Não registrar tokens Bearer em logs.

### Fase 2 — migrar consumidores

Para código dentro do monólito, usar diretamente serviços/selectors Python em vez de HTTP local. Para fluxos humanos, usar as views/formulários existentes. Para automações internas futuras, preferir jobs/comandos que chamem a camada de serviço.

Se existir integração externa real que ainda seja necessária, ela deve receber um plano explícito antes da desativação; a Spec 000 não autoriza substituí-la silenciosamente por uma nova API pública.

### Fase 3 — sinalizar depreciação

Documentar a API como legada, evitar novos consumidores e comunicar os responsáveis já inventariados. A criação de novos tokens pode ser restringida em uma mudança posterior, desde que os consumidores existentes estejam mapeados.

### Fase 4 — ensaio de desligamento

Desabilitar a API primeiro em ambiente não produtivo ou por configuração reversível. Executar testes das jornadas de arquivos e das integrações inventariadas. Corrigir qualquer dependência não prevista antes de prosseguir.

### Fase 5 — remoção

Somente após aprovação do mantenedor e evidência de que todos os consumidores necessários foram migrados, remover rotas, views da API e a emissão de tokens que não tenham outra finalidade. A remoção deve ser um PR separado para permitir revisão específica do impacto.

## Rollback

Enquanto a remoção não ocorrer, rollback significa manter/reabilitar as rotas legadas sem mudar os serviços de domínio. No PR futuro de remoção, preservar um caminho de reversão simples no primeiro ciclo de implantação (por exemplo, restauração do commit/flag de exposição), sem reintroduzir lógica de negócio duplicada.

## Critérios para considerar o inventário encerrado

T-CORE-01 é considerada atendida no nível do repositório porque a superfície e os consumidores versionados foram inventariados. A verificação de consumidores externos permanece como **gate operacional obrigatório para a remoção**, não como suposição.

T-CORE-03 é considerada atendida porque cada operação possui alternativa interna e existe uma sequência de migração/rollback definida. Nenhuma rota é removida por este documento.
