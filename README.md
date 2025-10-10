# Aegis Share - Compartilhamento de Arquivos Descentralizado
![IPFS Badge](https://img.shields.io/badge/IPFS-65C2CB?logo=ipfs&logoColor=fff&style=for-the-badge) ![Django Badge](https://img.shields.io/badge/Django-092E20?logo=django&logoColor=fff&style=for-the-badge) ![Bulma Badge](https://img.shields.io/badge/Bulma-00D1B2?logo=bulma&logoColor=fff&style=for-the-badge) ![htmx Badge](https://img.shields.io/badge/htmx-36C?logo=htmx&logoColor=fff&style=for-the-badge) ![Hyperscript](https://img.shields.io/badge/Hyperscript?style=for-the-badge&logo=https%3A%2F%2Fpypi-camo.freetls.fastly.net%2F3d02831378bb2b468530f40eb310c62fe8084761%2F68747470733a2f2f6769746875622e636f6d2f4c75634c6f7230362f646a616e676f2d68797065727363726970742f626c6f622f6d61696e2f646a616e676f2d68797065727363726970742e706e673f7261773d74727565)
 ![uv Badge](https://img.shields.io/badge/uv-DE5FE9?logo=uv&logoColor=fff&style=for-the-badge) ![Redis Badge](https://img.shields.io/badge/Redis-FF4438?logo=redis&logoColor=fff&style=for-the-badge) ![Docker Badge](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=fff&style=for-the-badge)

Este é um projeto Django que implementa um sistema de compartilhamento de arquivos utilizando **IPFS (InterPlanetary File System)** para armazenamento descentralizado e **WebSockets** (através de Django Channels) para notificação em tempo real sobre o status dos arquivos.

## Tecnologias Principais

  * **Django:** Framework web principal.
  * **IPFS:** Usado para armazenamento e recuperação de arquivos.
  * **Django Channels:** Habilita a funcionalidade de WebSockets.
  * **Redis:** Necessário como *channel layer* para os WebSockets.
  * **Docker/Docker Compose:** Para orquestração e fácil inicialização do ambiente.
  * **Granian:** Servidor ASGI para rodar o Django Channels.

-----

## Requisitos para funcionamento

Você tem duas maneiras principais de iniciar o projeto: usando **Docker Compose** (recomendado) ou usando **IPFS no Docker** junto com **Granian** após a instalação das dependências.

### Opção 1: Com Docker Compose (Recomendado)

Esta é a maneira mais fácil, pois o Docker Compose gerencia o Django, o Redis e o IPFS de uma só vez.

1.  **Pré-requisitos:** Certifique-se de ter [Docker](https://www.docker.com/get-started/) instalado.

2.  **Construir e Iniciar:** Na raiz do projeto, execute o seguinte comando:

    ```bash
    docker compose up --build
    ```

3.  **Acesso:** O projeto estará disponível em `http://localhost:8000`.

#### Aviso de Segurança em Testes com Docker

Se você estiver rodando o container **em um ambiente de teste ou CI/CD que não utilize HTTPS/SSL**, o Django provavelmente falhará devido às configurações de segurança estritas.

Para desativar a segurança e ativar o modo `DEBUG`, você deve garantir que a variável **`IS_DOCKER` seja configurada como `False`** no seu ambiente. Isso garante que as seguintes opções de desenvolvimento sejam ativadas, conforme o seu `settings.py`:

| Variável               | Valor para Teste Local | Valor Padrão no Docker |
|------------------------|------------------------|-------------------------|
| `DEBUG`                | `True`                 | `False`                 |
| `SECURE_SSL_REDIRECT`  | `False`                | `True`                  |
| `SESSION_COOKIE_SECURE`| `False`                | `True`                  |
| `CSRF_COOKIE_SECURE`   | `False`                | `True`                  |


-----

## Instalação das Dependências (Opção 2)

O projeto usa `pyproject.toml` para gerenciar dependências. Escolha seu gerenciador de pacotes preferido:

### Usando Poetry

1.  **Instale as dependências:**
    ```bash
    poetry install
    ```
2.  **Ative o ambiente virtual:**
    ```bash
    poetry shell
    ```

### Usando uv

1.  **Sincronize as dependências:**
    ```bash
    uv sync
    ```
2.  **Ative o ambiente virtual:**
    ```bash
    source .venv/bin/activate  # ou .venv\Scripts\activate no Windows
    ```

### Usando Pip Tradicional

1.  **Instale um ambiente virtual:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # ou .venv\Scripts\activate no Windows
    ```
2.  **Instale as dependências a partir do `pyproject.toml`:**
    ```bash
    pip install .
    ```

-----

## Execução (Opção 2)

Se você escolheu a Opção 2, siga estes passos após instalar as dependências.

#### Pré-requisitos de Serviço

1.  **IPFS Daemon:** O daemon do IPFS deve estar rodando e acessível.

    ```bash
    # Exemplo rodando IPFS via Docker
    docker run -d --name ipfs_host -p 5001:5001 ipfs/go-ipfs
    ```

#### Configuração e Execução do Django

1.  **Migrações:**

    ```bash
    python manage.py migrate
    ```

2.  **Iniciar o Servidor:** Use o **Granian** para servir o projeto com suporte a ASGI (WebSockets).

    ```bash
    Granian mysite.asgi:application --host 0.0.0.0 --port 8000 --interface asgi
    ```

3.  **Acesso:** O projeto estará disponível em `http://localhost:8000`.

-----

## Configurações Específicas

Certifique-se de que as seguintes variáveis de ambiente (ou configurações no `settings.py`) estejam corretas:

  * **`REDIS_URL`**: O endereço da sua instância Redis (padrão: `redis://127.0.0.1:6379/1`).
  * **`IPFS_HTTP_CLIENT_HOST`**: O endereço da API do seu daemon IPFS (padrão: `127.0.0.1`).
  * **`IPFS_HTTP_CLIENT_PORT`**: A porta da API do seu daemon IPFS (padrão: `5001`).
