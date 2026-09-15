# AGENTS.md — Projeto Django (YAGNI + Preguiçoso + Python-first + FBV-first)

Guia de comportamento para agentes de IA que atuam neste repositório Django.

> **Filosofia central:** *O melhor código é o código que não precisou ser escrito.*  
> Reutilize antes de criar. Escreva Python antes de escrever JavaScript.  
> Prefira funções explícitas a hierarquias de classes.  
> Se der para resolver em 3 linhas legíveis, não use 30 "por garantia".

---

## 1. Princípios não-negociáveis

### 1.1 YAGNI (You Aren't Gonna Need It)

- **Não** implemente features, abstrações, camadas, mixins, sinais ou services que não tenham um caso de uso **atual e concreto**.
- **Não** crie `BaseAbstractFactoryStrategyManager` "para o futuro".
- **Não** antecipe generalizações sem pelo menos um segundo caso de uso real.
- Se aparecer repetição ou um segundo caso concreto, **aí sim** refatore.
- Regra prática: se ninguém pediu e ninguém está usando hoje → não escreva.

### 1.2 Preguiça produtiva (DRY radical)

Antes de escrever qualquer função, classe ou módulo, **procure** se a solução já existe:

1. No próprio projeto (`rg`, `grep`, `find`).
2. No Django (`django.shortcuts`, `django.http`, `django.utils`, `django.db`, etc.).
3. Na stdlib do Python (`pathlib`, `functools`, `itertools`, `contextlib`, `collections`, etc.).
4. Em libs já instaladas (`requirements.txt`, `pyproject.toml`).
5. Só então: escreva algo novo.

Prefira, nesta ordem:

- funções simples;
- funções utilitárias já existentes;
- decorators;
- composição;
- classes apenas quando realmente agregarem.

**Função > classe**, salvo quando uma classe torna o código objetivamente menor, mais claro ou mais reutilizável.

### 1.3 Python-first

- **Sempre** prefira uma solução em Python antes de qualquer JavaScript.
- Se existir lib Python madura e apropriada, **ela vence**.
- Antes de escrever JS, considere:
  1. Django no servidor;
  2. HTML nativo;
  3. HTMX;
  4. Alpine.js para estado local mínimo;
  5. JS próprio apenas como último recurso.

JS próprio só é aceitável quando:

- a interação precisa acontecer no navegador sem round-trip razoável;
- HTML + HTMX não resolvem de forma simples;
- não existe equivalente Python razoável;
- ou o requisito exige uma biblioteca client-side específica.

### 1.4 FBV-first

Neste projeto, **Function Based Views (FBVs) são o padrão**.

Ao criar ou alterar uma view:

1. Tente resolver com uma função.
2. Use helpers e decorators nativos do Django.
3. Extraia regra de negócio apenas se houver necessidade real.
4. Só considere uma CBV se ela deixar a implementação **claramente mais simples** que a FBV.

**Não use CBV apenas porque existe uma generic view equivalente.**

Prefira:

```python
@login_required
def pedido_detalhe(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    return render(request, "pedidos/detalhe.html", {"pedido": pedido})
```

em vez de:

```python
class PedidoDetailView(LoginRequiredMixin, DetailView):
    model = Pedido
    template_name = "pedidos/detalhe.html"
    context_object_name = "pedido"
```

quando ambos resolvem exatamente o mesmo problema.

A preferência por FBV existe porque ela tende a deixar explícitos:

- entrada (`request`);
- permissões;
- query;
- fluxo GET/POST;
- redirects;
- respostas;
- tratamento de erro.

**Regra:** se for necessário abrir vários arquivos ou conhecer a hierarquia de mixins para entender a view, provavelmente a solução está complexa demais.

---

## 2. Hierarquia de decisão

Ao resolver qualquer problema, siga esta ordem e **pare na primeira opção que resolver de forma limpa**:

1. Já existe no projeto? → **reuse**.
2. Django já possui função/helper/decorator nativo? → **use**.
3. Uma **FBV simples** resolve? → **prefira**.
4. Django ORM / Forms / Admin / middleware resolvem? → **use**.
5. Stdlib do Python resolve? → **use**.
6. Lib Python já instalada resolve? → **use**.
7. Lib Python leve e madura resolve melhor? → instale apenas se houver benefício real.
8. HTML + HTMX resolve? → use.
9. Alpine.js mínimo resolve? → use apenas para estado client-side pequeno.
10. JS próprio resolve? → último recurso.
11. SPA / framework frontend → somente com requisito explícito e justificativa forte.

### Exceção: quando uma CBV é aceitável

CBV não é proibida. Ela é uma **exceção consciente**.

Use CBV apenas quando pelo menos uma destas condições for verdadeira:

- reduz significativamente código repetitivo;
- aproveita comportamento realmente útil de uma generic view sem exigir overrides confusos;
- existe padrão consolidado no próprio projeto que deve ser mantido;
- uma implementação equivalente em FBV ficaria maior ou menos legível;
- a composição de comportamento é realmente mais clara com a classe.

**Não use CBV para demonstrar conhecimento do framework. Use apenas se simplificar.**

---

## 3. Preferências de stack

| Necessidade | Prefira | Evite |
|---|---|---|
| Views | **FBV + helpers/decorators Django** | CBV por padrão |
| GET/POST simples | `request.method`, Forms, `render`, `redirect` | abstração genérica |
| Objeto ou 404 | `get_object_or_404()` | `try/except DoesNotExist` repetitivo |
| Lista ou 404 | `get_list_or_404()` quando fizer sentido | boilerplate |
| Restrição HTTP | `@require_GET`, `@require_POST`, `@require_http_methods` | validação manual |
| Auth | `@login_required`, `permission_required()` | auth própria |
| Mensagens | `django.contrib.messages` | sistema de flash próprio |
| Formulários | `django.forms`, `ModelForm` | validação manual em view/JS |
| UI reativa leve | HTMX + Django templates | React/Vue só para isso |
| Interatividade pontual | Alpine.js | jQuery/framework pesado |
| Admin custom | `django.contrib.admin` | CRUD caseiro |
| API simples | FBV + `JsonResponse` | DRF para 1–2 endpoints triviais |
| API estruturada | Django Ninja/DRF se já adotado e necessário | framework novo sem necessidade |
| ORM | QuerySets + expressions Django | SQL manual sem motivo |
| Query complexa reutilizada | função/selectors **só quando necessário** | repository pattern automático |
| Regra de negócio reutilizada | função em `services.py` **só quando necessário** | Service classes genéricas |
| Tasks assíncronas | solução já existente no projeto; `django-q2`/`huey` se necessário | Celery/Redis "por padrão" |
| Settings | `django-environ` se já usado | parser próprio |
| Datas/horas | `zoneinfo`, `datetime`, `django.utils.timezone` | `pytz` |
| Templates | DTL | Jinja "porque sim" |
| Testes | `pytest-django` + `factory_boy` | boilerplate excessivo |
| Filtros | `django-filter` se necessário | filtros duplicados em várias views |
| CSV | `csv` da stdlib | geração client-side |
| Excel | `openpyxl` | geração client-side |
| PDF | `weasyprint` | Puppeteer/JS sem necessidade |
| Imagens | `Pillow` | processamento no browser |
| Markdown | `markdown` / `mistune` | `marked.js` |
| Gráficos | `matplotlib` server-side quando adequado | Chart.js sem necessidade |

**Regra de ouro:** se você está prestes a criar uma classe ou escrever JavaScript, pare e pergunte:

> *"Uma função Python simples resolve isso melhor?"*

---

## 4. Convenções Django deste projeto

### 4.1 Estrutura

```text
config/           # settings, urls, wsgi/asgi
apps/
  <app>/
    models.py     # dados + comportamento simples ligado ao modelo
    views.py      # preferencialmente FBVs finas e explícitas
    forms.py
    urls.py
    admin.py
    services.py   # somente se houver regra de negócio reutilizada
    selectors.py  # somente se houver query complexa reutilizada
    templates/
      <app>/
        _partials/
    tests/
```

> **Não crie** `services.py`, `selectors.py`, `repositories.py`, `interfaces.py`, `dtos.py`, `use_cases.py` ou diretórios equivalentes apenas "por arquitetura".  
> Crie **quando houver dor real**.

Se o app for pequeno, é perfeitamente aceitável manter:

```text
models.py
views.py
forms.py
urls.py
```

e nada além disso.

### 4.2 Models

- Use `TextChoices` para enums.
- Use `Meta.constraints` e `indexes` quando houver necessidade real.
- Prefira `UniqueConstraint` quando aplicável.
- `__str__` deve retornar representação útil.
- Prefira `@property` / `@cached_property` para valores derivados simples.
- Não coloque chamadas HTTP, envio de e-mail ou acesso a serviço remoto em models.
- Não transforme model em "service container".
- Use métodos de model quando o comportamento pertence naturalmente àquela entidade.

### 4.3 Views — FBV por padrão

**Toda nova view deve começar como FBV**, salvo motivo concreto para não fazê-lo.

Exemplo GET:

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .models import Pedido


@login_required
def pedido_detalhe(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)

    return render(
        request,
        "pedidos/detalhe.html",
        {"pedido": pedido},
    )
```

Exemplo GET/POST:

```python
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import PedidoForm
from .models import Pedido


@login_required
def pedido_editar(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    form = PedidoForm(request.POST or None, instance=pedido)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Pedido atualizado com sucesso.")
        return redirect("pedidos:detalhe", pk=pedido.pk)

    return render(
        request,
        "pedidos/form.html",
        {"form": form, "pedido": pedido},
    )
```

### Regras para FBVs

- Use `@login_required`.
- Use `@permission_required` quando adequado.
- Use `@require_GET`, `@require_POST` ou `@require_http_methods` para restringir métodos.
- Use `get_object_or_404()` em vez de repetir `try/except`.
- Use `redirect()` e `render()` diretamente.
- Use `messages` para feedback após redirect.
- Use forms para validação de entrada.
- Use `transaction.atomic()` quando uma operação realmente precisar ser atômica.
- Use early returns para reduzir nesting.
- Não coloque centenas de linhas em uma FBV: extraia **funções específicas**, não classes genéricas.
- Otimize queries com `select_related()` e `prefetch_related()` quando necessário.
- Não faça query dentro de loop se ela puder ser feita antes.

### Quando NÃO migrar uma CBV existente

Não converta CBV para FBV apenas por estilo quando:

- ela já é pequena e estável;
- a mudança não traz benefício concreto;
- a conversão gera risco sem ganho de legibilidade;
- existe comportamento herdado importante e bem compreendido.

**FBV-first vale principalmente para código novo e refactors que já são necessários.**

### Quando considerar uma CBV

Antes de criar uma CBV, responda:

1. A FBV ficaria realmente mais complexa?
2. A generic view elimina código relevante?
3. Vou precisar de poucos ou nenhum override?
4. A herança fica óbvia para quem lê?
5. Já existe padrão equivalente neste app?

Se a resposta for "não" para a maioria, use FBV.

### Evite em CBVs

- cadeia grande de mixins;
- overrides de `dispatch()`, `get()`, `post()`, `form_valid()`, `get_context_data()` e `get_queryset()` na mesma classe;
- herança em múltiplos níveis;
- classes base internas sem necessidade;
- mixin usado uma única vez;
- lógica de negócio escondida em métodos lifecycle.

Se uma CBV precisa disso tudo, uma FBV provavelmente ficará mais clara.

### 4.4 Forms

- Use `ModelForm` sempre que o formulário representa um model.
- Validação de entrada pertence ao form.
- Validação de um campo → `clean_<campo>()`.
- Validação entre campos → `clean()`.
- Não replique validação de form na view.
- Não faça validação de negócio complexa em JavaScript como fonte principal.
- Widgets customizados somente quando o padrão não atende.

### 4.5 Templates

- Use `{% extends %}` e `{% block %}`.
- Reuse HTML com `{% include %}`.
- Coloque parciais reutilizáveis em `_partials/`.
- Evite lógica de negócio no template.
- Use HTMX para requests parciais simples.
- Uma resposta HTMX deve preferencialmente retornar um fragmento de template, não HTML montado em Python.

### 4.6 URLs

- Sempre use `path()` / `re_path()` com `name=`.
- Use namespaces de app.
- Use `reverse()`, `reverse_lazy()` ou `{% url %}`.
- **Nunca** hardcode URLs internas.
- Em FBVs, passe a própria função diretamente:

```python
from django.urls import path

from . import views

app_name = "pedidos"

urlpatterns = [
    path("", views.pedido_lista, name="lista"),
    path("<int:pk>/", views.pedido_detalhe, name="detalhe"),
    path("<int:pk>/editar/", views.pedido_editar, name="editar"),
]
```

Evite `.as_view()` quando uma função simples resolver.

---

## 5. Organização da lógica

A existência de uma FBV não significa colocar tudo dentro dela.

A view deve:

1. receber o request;
2. validar acesso;
3. obter/validar entrada;
4. chamar código de domínio quando necessário;
5. montar a resposta.

### Deixe na própria view quando

- a regra é curta;
- é usada apenas ali;
- fica clara;
- não dificulta testes.

### Extraia uma função quando

- o bloco possui uma responsabilidade clara;
- deixa a view significativamente mais legível;
- pode ser testado isoladamente;
- há reutilização real ou provável no contexto atual.

Exemplo:

```python
def calcular_total(itens):
    return sum(item.valor for item in itens)
```

não:

```python
class TotalPedidoCalculationService:
    def execute(self, itens):
        ...
```

### Crie `services.py` somente quando

- existe regra de negócio relevante;
- a regra é usada por mais de uma entrada (view, command, task, API);
- ou separar a regra da camada HTTP traz benefício concreto.

Mesmo em `services.py`, **prefira funções**.

```python
def confirmar_pagamento(pedido, pagamento):
    ...
```

em vez de:

```python
class ConfirmarPagamentoService:
    ...
```

salvo necessidade real de estado/objeto.

---

## 6. ORM e performance

Prefira o ORM do Django.

### Evite N+1

Use:

```python
Pedido.objects.select_related("cliente")
```

ou:

```python
Pedido.objects.prefetch_related("itens")
```

quando a template/view acessar essas relações em uma lista.

### Prefira operações em banco

Use:

- `filter()`;
- `exclude()`;
- `exists()`;
- `values()`;
- `values_list()`;
- `annotate()`;
- `aggregate()`;
- `F()`;
- `Q()`;
- `Subquery()` somente quando realmente necessário;
- `bulk_create()` / `bulk_update()` para lotes quando fizer sentido.

Evite carregar milhares de objetos em Python para fazer algo que o banco resolve diretamente.

### Não otimize por adivinhação

- Não adicione cache "por garantia".
- Não crie índices sem necessidade.
- Não faça raw SQL sem necessidade.
- Não introduza Redis apenas por performance hipotética.

Meça primeiro quando a otimização não for óbvia.

---

## 7. Estilo de código Python

Siga **PEP 8** e o **Zen of Python** (`import this`).

```python
# Bom: simples, direto e pythonico
def active_users():
    return User.objects.filter(is_active=True)
```

```python
# Ruim: cerimônia desnecessária
class UserServiceFactory:
    def get_active_users(self) -> list[User]:
        qs = User.objects.all()
        result = []

        for user in qs:
            if user.is_active:
                result.append(user)

        return result
```

Diretrizes:

- funções pequenas e focadas;
- nomes claros;
- early return > nesting;
- type hints onde agregam clareza;
- não anote o óbvio;
- `pathlib.Path` > `os.path`;
- f-strings > `%` / `.format()`;
- comprehensions quando continuarem legíveis;
- `enumerate`, `zip`, `itertools` > controle manual;
- context managers (`with`) > cleanup manual;
- `dataclasses` quando houver objeto de dados real;
- `cached_property` / `lru_cache` somente quando fizer sentido;
- exceções específicas > `except Exception`;
- `logging` > `print()`;
- constantes nomeadas > valores mágicos repetidos.

### Não confunda "Pythonic" com código esperto

Evite:

- one-liners difíceis de ler;
- metaclasses;
- decorators customizados sem necessidade;
- descriptors;
- generics excessivos;
- ABCs sem múltiplas implementações reais.

Legibilidade ganha.

---

## 8. Tratamento de erros

- Erros não devem passar silenciosamente.
- Capture apenas exceções que você consegue tratar.
- Evite:

```python
try:
    ...
except Exception:
    pass
```

Prefira:

```python
try:
    ...
except Pedido.DoesNotExist:
    ...
```

ou, em views:

```python
pedido = get_object_or_404(Pedido, pk=pk)
```

Use logging quando a falha for operacional e relevante:

```python
logger.exception("Erro ao processar pedido %s", pedido.pk)
```

Não exponha traceback ou dados internos ao usuário final.

---

## 9. Transações

Use `transaction.atomic()` apenas quando múltiplas alterações precisarem ser confirmadas ou revertidas juntas.

```python
from django.db import transaction


@transaction.atomic
def confirmar_pedido(pedido):
    ...
```

Não envolva toda view em transação sem necessidade.

Evite chamadas HTTP externas dentro de uma transação longa sempre que possível.

---

## 10. Testes

Use **pytest-django** + **factory_boy** quando já estiverem disponíveis no projeto.

Prioridades:

1. regras de negócio;
2. permissões;
3. fluxos GET/POST relevantes;
4. comportamento diante de dados inválidos;
5. regressões de bugs reais.

Para FBVs, teste comportamento HTTP:

```python
def test_editar_pedido_exige_login(client, pedido):
    response = client.get(
        reverse("pedidos:editar", kwargs={"pk": pedido.pk})
    )

    assert response.status_code == 302
```

Não teste detalhes internos da função quando o comportamento HTTP basta.

Não teste o Django por ele mesmo.

Evite testar:

- se `render()` funciona;
- se `get_object_or_404()` retorna 404;
- se um `ModelForm` básico salva sem existir regra própria.

**Um teste por regra real é melhor que dezenas de testes cerimoniais.**

---

## 11. Dependências

Antes de instalar uma dependência:

1. Django já resolve?
2. Python stdlib já resolve?
3. Já existe biblioteca instalada que resolve?
4. Implementar diretamente é trivial e seguro?
5. A nova dependência economiza complexidade de verdade?

Se instalar:

- escolha projeto mantido;
- evite dependência gigantesca para problema pequeno;
- registre a justificativa;
- não adicione alternativa concorrente a algo já usado no projeto sem necessidade.

---

## 12. O que este agente NUNCA deve fazer

- Escolher CBV automaticamente.
- Criar CBV apenas porque existe uma generic view equivalente.
- Criar mixin para uso único.
- Criar uma hierarquia de classes para substituir funções simples.
- Criar abstrações "para o futuro".
- Adicionar dependência JS sem tentar Python/HTMX antes.
- Escrever React/Vue/SPA sem pedido explícito.
- Criar `services/`, `repositories/`, `selectors/`, `interfaces/` por padrão.
- Duplicar lógica já existente.
- Reinventar `django.contrib.*`.
- Adicionar Celery/Redis/Kafka "porque é padrão".
- Usar `pytz` em código novo.
- Fazer over-engineering com Generics/ABCs.
- Esconder fluxo simples atrás de abstrações.
- Comentar o óbvio.
- Deixar `print()` no código de aplicação.
- Ignorar N+1.
- Capturar `Exception` silenciosamente.
- Fazer query dentro de loop sem necessidade.
- Hardcodar URL interna.
- Colocar validação de formulário na view.
- Criar JavaScript para algo que Django + HTMX resolve facilmente.

---

## 13. Checklist antes de finalizar uma alteração

### Reutilização e simplicidade

- [ ] Procurei implementação equivalente no projeto?
- [ ] Estou reutilizando Django/stdlib antes de criar algo?
- [ ] Existe alguma abstração criada apenas "por garantia"?
- [ ] O código ficou mais simples que a alternativa?

### Views

- [ ] Tentei uma **FBV primeiro**?
- [ ] Se usei CBV, ela ficou comprovadamente mais simples que a FBV?
- [ ] Evitei mixins desnecessários?
- [ ] Usei decorators nativos quando possível?
- [ ] Usei `get_object_or_404`, `render`, `redirect` e helpers nativos?
- [ ] A view está fina e legível?
- [ ] Validação está no form?

### Banco

- [ ] Há N+1?
- [ ] Preciso de `select_related()`?
- [ ] Preciso de `prefetch_related()`?
- [ ] Existe query dentro de loop?
- [ ] O banco poderia fazer a operação melhor que Python?

### Frontend

- [ ] Consigo fazer em Python em vez de JS?
- [ ] Consigo fazer com HTML nativo?
- [ ] Consigo usar HTMX?
- [ ] JS adicionado é realmente necessário?

### Qualidade

- [ ] Todos os imports são usados?
- [ ] Não deixei `print()`?
- [ ] Não há `except Exception: pass`?
- [ ] URLs usam `reverse()` / `{% url %}`?
- [ ] Testes cobrem regras reais?
- [ ] Se adicionei dependência, existe justificativa concreta?

---

## 14. Como o agente deve responder

Ao propor código para este projeto:

1. **Informe primeiro qual nível da hierarquia da seção 2 foi usado.**
2. **Prefira FBV** em qualquer nova view, salvo justificativa concreta.
3. Mostre a solução mais simples que resolve completamente.
4. Diga o que foi reutilizado do projeto/Django/Python.
5. Aponte o que deliberadamente **não** foi criado por YAGNI.
6. Se houver risco de N+1 ou duplicação, destaque.
7. Se uma CBV parecer conveniente, compare mentalmente com a FBV antes de escolhê-la.
8. Se o usuário pedir algo excessivamente complexo, apresente primeiro a alternativa mais simples.
9. Não proponha arquitetura adicional sem necessidade atual.
10. Não transforme uma alteração pequena em refactor amplo sem pedido explícito.

### Formato preferencial ao sugerir implementação

Use, quando fizer sentido:

```text
Nível usado: 2/3 — Django nativo + FBV.

Reuso:
- get_object_or_404
- login_required
- ModelForm

Implementação:
[código]

YAGNI:
- não criei service;
- não criei mixin;
- não criei CBV;
- não adicionei JavaScript.
```

---

## 15. Regra final

Quando houver duas soluções corretas, escolha nesta ordem:

1. a que já existe;
2. a que usa Django nativo;
3. a que usa uma **função Python simples**;
4. a que tem menos conceitos;
5. a que exige menos arquivos;
6. a que exige menos dependências;
7. a que é mais fácil de apagar amanhã.

> **FBV por padrão. Classes por necessidade. JavaScript por exceção.**
>
> **Código preguiçoso ≠ código ruim.**  
> O melhor código é aquele que resolve o problema com o mínimo de abstração necessário.
