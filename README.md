Absolutamente. Vou refinar a seção do Docker para enfatizar que, ao rodar a imagem em um ambiente que não é de produção (como um teste local ou CI/CD que não simula HTTPS), você precisa garantir que o **`IS_DOCKER`** seja configurado como `False` ou que as variáveis de segurança sejam desativadas.

Aqui está o `README.md` revisado:

-----

# 📁 IPFS FileShare - Compartilhamento de Arquivos Descentralizado

Este é um projeto Django que implementa um sistema de compartilhamento de arquivos utilizando **IPFS (InterPlanetary File System)** para armazenamento descentralizado e **WebSockets** (através de Django Channels) para notificação em tempo real sobre o status dos arquivos.

## 🚀 Tecnologias Principais

  * **Django:** Framework web principal.
  * **IPFS:** Usado para armazenamento e recuperação de arquivos.
  * **Django Channels:** Habilita a funcionalidade de WebSockets.
  * **Redis:** Necessário como *channel layer* para os WebSockets.
  * **Docker/Docker Compose:** Para orquestração e fácil inicialização do ambiente.
  * **Uvicorn:** Servidor ASGI para rodar o Django Channels.

-----

## 🛠️ Como Fazer Funcionar

Você tem duas maneiras principais de iniciar o projeto: usando **Docker Compose** (recomendado) ou usando **Redis local/Docker** junto com **Uvicorn** após a instalação das dependências.

### Opção 1: Com Docker Compose (Recomendado)

Esta é a maneira mais fácil. O Docker Compose gerencia o Django, o Redis e o IPFS de uma só vez, **configurando automaticamente as variáveis de segurança para produção (HTTPS) ao usar `IS_DOCKER=True`**.

1.  **Pré-requisitos:** Certifique-se de ter o [Docker](https://www.docker.com/get-started/) e o [Docker Compose](https://docs.docker.com/compose/install/) instalados.

2.  **Construir e Iniciar:** Na raiz do projeto, execute o seguinte comando:

    ```bash
    docker-compose up --build
    ```

3.  **Acesso:** O projeto estará disponível em `http://localhost:8000`.

#### Aviso de Segurança em Testes com Docker

Se você estiver rodando o container **em um ambiente de teste ou CI/CD que não utilize HTTPS/SSL**, o Django vai falhar devido às configurações de segurança estritas.

Para desativar a segurança e ativar o modo `DEBUG`, você deve garantir que a variável **`IS_DOCKER` seja configurada como `False`** no seu ambiente. Isso garante que as seguintes opções de desenvolvimento sejam ativadas, conforme o seu `settings.py`:

| Variável               | Valor para Teste Local | Valor Padrão no Docker |
|------------------------|------------------------|-------------------------|
| `DEBUG`                | `True`                 | `False`                 |
| `SECURE_SSL_REDIRECT`  | `False`                | `True`                  |
| `SESSION_COOKIE_SECURE`| `False`                | `True`                  |
| `CSRF_COOKIE_SECURE`   | `False`                | `True`                  |

-----

## 📦 Instalação das Dependências (Para Opção 2)

O projeto usa `pyproject.toml` para gerenciar dependências. Escolha seu gerenciador de pacotes preferido:

### Usando Poetry

1.  **Instale o Poetry.**
2.  **Instale as dependências:** `poetry install`
3.  **Ative o ambiente virtual:** `poetry shell`

### Usando uv

1.  **Instale o uv.**
2.  **Crie e ative um ambiente virtual (opcional):** `uv venv` e `source .venv/bin/activate`
3.  **Sincronize as dependências:** `uv sync`

### Usando Pip Tradicional

1.  **Instale um ambiente virtual (opcional):** `python -m venv venv` e ative-o.
2.  **Instale as dependências:** `pip install .`

-----

## 🏃 Execução (Opção 2)

Se você escolheu a Opção 2 (rodar localmente), siga estes passos após instalar as dependências.

#### Pré-requisitos de Serviço

1.  **IPFS Daemon:** O daemon do IPFS deve estar rodando (porta padrão `5001`).
2.  **Redis:** Uma instância do Redis deve estar rodando (porta padrão `6379`).

#### Configuração de Ambiente e Execução do Django

Ao rodar localmente, o **`IS_DOCKER` deve ser `False`** para que você possa usar o servidor de desenvolvimento via HTTP e com `DEBUG=True`.

1.  **Migrações:**

    ```bash
    python manage.py migrate
    ```

2.  **Iniciar o Servidor:** Use o **Uvicorn** para servir o projeto com suporte a ASGI (WebSockets).

    ```bash
    uvicorn project_name.asgi:application --host 0.0.0.0 --port 8000
    ```

    *(Substitua `project_name` pelo nome real da sua pasta de projeto Django.)*

3.  **Acesso:** O projeto estará disponível em `http://localhost:8000`.

-----

## ⚙️ Configurações Essenciais

Certifique-se de que as seguintes configurações (variáveis de ambiente ou `settings.py`) estejam corretas para o seu ambiente:

  * **`IS_DOCKER`**: Define o modo de segurança (veja tabela acima).
  * **`REDIS_URL`**: Endereço da instância Redis (padrão: `redis://127.0.0.1:6379/1`).
  * **`IPFS_HTTP_CLIENT_HOST`**: Endereço da API do daemon IPFS (padrão: `127.0.0.1`).
  * **`IPFS_HTTP_CLIENT_PORT`**: Porta da API do daemon IPFS (padrão: `5001`).