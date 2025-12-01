# Aegis Share - Compartilhamento de Arquivos Descentralizado
![IPFS Badge](https://img.shields.io/badge/IPFS-65C2CB?logo=ipfs&logoColor=fff&style=for-the-badge) ![Django Badge](https://img.shields.io/badge/Django-092E20?logo=django&logoColor=fff&style=for-the-badge) ![Bulma Badge](https://img.shields.io/badge/Bulma-00D1B2?logo=bulma&logoColor=fff&style=for-the-badge) ![htmx Badge](https://img.shields.io/badge/htmx-36C?logo=htmx&logoColor=fff&style=for-the-badge)
![uv Badge](https://img.shields.io/badge/uv-DE5FE9?logo=uv&logoColor=fff&style=for-the-badge) ![Redis Badge](https://img.shields.io/badge/Redis-FF4438?logo=redis&logoColor=fff&style=for-the-badge)
![Docker Badge](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=fff&style=for-the-badge)

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
### DOT ENV
Altere o arquivo .env para oque é apropriado para cada projeto 

### Dependências e inicio do servidor
Existem duas maneiras principais de iniciar o projeto: usando Docker Compose ou usando Ambiente de Desenvolvimento após a instalação das dependências.

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
2.  **Rode Migrations com Poetry:**
    ```bash
    poetry run task migrate
    ```
3.  **Rode o Servidor com Poetry:**
    ```bash
    poetry run task server
    ```

### Usando uv

1.  **Sincronize as dependências:**
    ```bash
    uv sync
    ```
2.  **Rode Migrations com UV:**
    ```bash
    uv run task migrate
    ```
3.  **Rode o Servidor com UV:**
    ```bash
    uv run task server
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
3. **Rode os comandos com python dentro da venv:**
    ```bash
    python (manage.py) <comando>
    ```

-----

## Execução (Opção 2)

Se você escolheu a Opção 2, siga estes passos após instalar as dependências.

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
