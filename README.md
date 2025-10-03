# 📁 IPFS FileShare - Compartilhamento de Arquivos Descentralizado
![IPFS Badge](https://img.shields.io/badge/IPFS-65C2CB?logo=ipfs&logoColor=fff&style=for-the-badge)![Django Badge](https://img.shields.io/badge/Django-092E20?logo=django&logoColor=fff&style=for-the-badge)![Bootstrap Badge](https://img.shields.io/badge/Bootstrap-7952B3?logo=bootstrap&logoColor=fff&style=for-the-badge)![uv Badge](https://img.shields.io/badge/uv-DE5FE9?logo=uv&logoColor=fff&style=for-the-badge)![Redis Badge](https://img.shields.io/badge/Redis-FF4438?logo=redis&logoColor=fff&style=for-the-badge)![Docker Badge](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=fff&style=for-the-badge)

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

Esta é a maneira mais fácil, pois o Docker Compose gerencia o Django, o Redis e o IPFS de uma só vez.

1.  **Pré-requisitos:** Certifique-se de ter [Docker](https://www.docker.com/get-started/) instalado.

2.  **Construir e Iniciar:** Na raiz do projeto, execute o seguinte comando:

    ```bash
    docker-compose up --build
    ```

3.  **Acesso:** O projeto estará disponível em `http://localhost:8000`.

-----

## 📦 Instalação das Dependências (Para Opção 2)

O projeto usa `pyproject.toml` para gerenciar dependências. Escolha seu gerenciador de pacotes preferido:

### Usando Poetry

1.  **Instale o Poetry.**
2.  **Instale as dependências:**
    ```bash
    poetry install
    ```
3.  **Ative o ambiente virtual:**
    ```bash
    poetry shell
    ```

### Usando uv

1.  **Instale o uv.**
2.  **Crie e ative um ambiente virtual (opcional, mas recomendado):**
    ```bash
    uv venv
    source .venv/bin/activate  # ou .venv\Scripts\activate no Windows
    ```
3.  **Sincronize as dependências:**
    ```bash
    uv sync
    ```

### Usando Pip Tradicional

1.  **Instale um ambiente virtual (opcional, mas recomendado):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # ou venv\Scripts\activate no Windows
    ```
2.  **Instale as dependências a partir do `pyproject.toml`:**
    ```bash
    pip install .
    ```

-----

## 🏃 Execução (Opção 2)

Se você escolheu a Opção 2, siga estes passos após instalar as dependências.

#### Pré-requisitos de Serviço

1.  **IPFS Daemon:** O daemon do IPFS deve estar rodando e acessível.

    ```bash
    # Exemplo rodando IPFS via Docker
    docker run -d --name ipfs_host -p 5001:5001 ipfs/go-ipfs
    ```

2.  **Redis:** Uma instância do Redis (o *channel layer* dos WebSockets) deve estar rodando.

    ```bash
    # Exemplo rodando Redis via Docker
    docker run -d --name redis_host -p 6379:6379 redis
    ```

#### Configuração e Execução do Django

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

## ⚙️ Configurações

Certifique-se de que as seguintes variáveis de ambiente (ou configurações no `settings.py`) estejam corretas:

  * **`REDIS_URL`**: O endereço da sua instância Redis (padrão: `redis://127.0.0.1:6379/1`).
  * **`IPFS_HTTP_CLIENT_HOST`**: O endereço da API do seu daemon IPFS (padrão: `127.0.0.1`).
  * **`IPFS_HTTP_CLIENT_PORT`**: A porta da API do seu daemon IPFS (padrão: `5001`).