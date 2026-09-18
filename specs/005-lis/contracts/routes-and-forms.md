# Contratos HTTP e formulários — LIS v1

Namespace `lis`. Sessão e profissional interno obrigatórios. Todas as rotas exigem `view_orders`, escopo PEP atual e CSRF nos POSTs.

| Método | URL | FBV | Template | Capacidade adicional |
|---|---|---|---|---|
| GET | `/laboratorio/pedidos/` | `order_list` | `clinical/lis/order_list.html` | — |
| GET/POST | `/laboratorio/encontros/<uuid:encounter_id>/pedidos/novo/` | `order_create` | `clinical/lis/order_form.html` | order_test |
| GET | `/laboratorio/pedidos/<uuid:pk>/` | `order_detail` | `clinical/lis/order_detail.html` | — |
| GET/POST | `/laboratorio/pedidos/<uuid:pk>/coleta/` | `specimen_create` | `clinical/lis/specimen_form.html` | collect_specimen |

Lista admite apenas `page` e `status` (`requested`, `collected` ou vazio). Filtro inválido apresenta erro, sem ampliar escopo. URLs com reverse/url; nada de nomes ou códigos clínicos em query strings.

- Sem sessão: login. Capacidade ausente: 403. Objeto fora do escopo: 404.
- Sucesso ou retry equivalente autorizado: 302 ao detalhe. Erro de campo: HTML 200. Conflito de estado/chave/coleta: 409. Falha de banco: 503 genérico, sem dados internos. Métodos indevidos: 405.
- GET de coleta já registrada redireciona ao detalhe; POST diferente retorna conflito.
- Respostas sensíveis têm `private, no-store`, `Vary: Cookie`, `nosniff`, inclusive redirects/erros.

## Forms

`OrderForm`: `lab_test` ModelChoiceField limitado a ativos e `operation_key` UUID hidden, novo no GET e preservado em erros. Encontro vem exclusivamente da URL autorizada. Código/nome/material são copiados pelo servidor, nunca aceitos do POST. Erro de catálogo: “Selecione um exame disponível.”

`SpecimenForm`: `accession_code` obrigatório até 64 caracteres, trim externo; `collected_at` obrigatório com timezone; `confirmed` BooleanField obrigatório (“Confirme que conferiu o paciente, o pedido e a identificação da amostra”); `operation_key` UUID hidden. Pedido/ator/material definidos pelo servidor. Coleta não pode anteceder `requested_at` nem estar no futuro. Mensagens não revelam a quem pertence código já utilizado.

Catálogo Admin: campos de texto obrigatórios após trim; código único; somente profissionais internos com permissões nativas de manutenção acessam o catálogo. Dados de teste exclusivamente sintéticos.

## Transação e retries

Ordem de locks: encontro → pedido (na coleta). Revalidar capacidade, escopo e encontro aberto dentro da transação antes de gravar; nunca confiar na validação do GET. Na criação, reler e bloquear LabTest antes de copiar seu retrato/confirmar ativo. Sem chamadas externas na transação.

Buscar operation_key existente somente após autorização. Retry compara ator, objeto de origem e campos normalizados; no pedido compara o ID do exame, preservando o retrato original mesmo se o catálogo mudar. Na coleta compara pedido, código, instante e confirmação. Não revelar objeto associado a chave de outro ator. Retry não cria segundo CREATE, mas audita o acesso ao registro devolvido.

Unicidade concorrente deve ser tratada fora do bloco atomic/savepoint que falhou; reler e aplicar a mesma regra de equivalência. Não capturar IntegrityError e continuar consultando dentro de transação quebrada. Toda falha de auditoria reverte a escrita.

## Eventos e PWA

Nenhum consumidor atual requer evento LIS; não criar canal, worker ou barramento. A trilha auditlog é obrigatória. A futura integração definirá contratos de eventos antes de publicar.

Service worker existente continua network-only para as novas rotas. Não cadastrar operação na fila offline. Falha de rede não pode confirmar coleta/pedido; orientar consulta ao histórico após reconexão, pois resposta perdida pode corresponder a gravação concluída.
