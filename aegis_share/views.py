from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from .forms import ClienteForm, FirstUserForm, FormUserADM, FotoForm, IPFSForm
from .models import Conversation, CustomUser, IPFSFile, Message
from .utils import arquivos_por_permissao, dar_acesso, imagem_para_base64, uploadipfs

User = get_user_model()


class FirstSuperuserCreateView(View):
    template_name = "primeiro_cadastro.html"

    def get(self, request):
        if User.objects.filter(is_superuser=True).exists():
            return redirect("home")

        form = FirstUserForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = FirstUserForm(request.POST)

        if User.objects.filter(is_superuser=True).exists():
            return redirect("home")

        if form.is_valid():
            user = form.save()

            login(request, user)
            return redirect("home")

        return render(request, self.template_name, {"form": form})


# Ajax / HTMX
@login_required
def buscar_cliente(request):
    term = request.GET.get("term", "")
    clientes = CustomUser.objects.filter(nivel_permissao="CLI").filter(
        username__icontains=term
    )[:10]
    results = [{"id": c.id, "nome": c.username} for c in clientes]
    return JsonResponse(results, safe=False)


@login_required
def buscar_funcionario(request):
    term = request.GET.get("term", "")
    funcionarios = CustomUser.objects.filter(nivel_permissao="FUNC").filter(
        username__icontains=term
    )[:10]
    results = [{"id": c.id, "nome": c.username} for c in funcionarios]
    return JsonResponse(results, safe=False)


@login_required
def buscar_arquivo(request):
    arquivos = arquivos_por_permissao(request.user)

    nome_filtro = request.GET.get("nome", "")
    dono_filtro = request.GET.get("dono", "")
    data_min_filtro = request.GET.get("data_min", "").strip()
    data_max_filtro = request.GET.get("data_max", "").strip()
    ordenar = request.GET.get("ordenar")

    if ordenar == "tamano_menor":
        arquivos = arquivos.order_by("-tamanho_arquivo")
    elif ordenar == "tamanho_maior":
        arquivos = arquivos.order_by("tamanho_arquivo")

    if nome_filtro:
        arquivos = arquivos.filter(nome_arquivo__icontains=nome_filtro)

    if dono_filtro:
        arquivos = arquivos.filter(dono_arquivo__username__icontains=dono_filtro)

    if data_min_filtro and len(data_min_filtro) == 10:
        try:
            data_min_obj = datetime.strptime(data_min_filtro, "%d/%m/%Y").date()
            arquivos = arquivos.filter(data_adicionado__date__gte=data_min_obj)
        except ValueError:
            pass

    if data_max_filtro and len(data_max_filtro) == 10:
        try:
            data_max_date = datetime.strptime(data_max_filtro, "%d/%m/%Y").date()

            data_limite = data_max_date + timedelta(days=1)

            arquivos = arquivos.filter(data_adicionado__lt=data_limite)

        except ValueError:
            pass

    if request.headers.get("HX-Request"):
        return render(request, "arquivos/htmx_arquivos.html", {"arquivos": arquivos})

    return render(request, "arquivos/arquivos.html", {"arquivos": arquivos})


# Views Padrões
def home(request):
    if request.user.is_authenticated:
        return render(request, "home/homecomlogin.html")
    else:
        return render(request, "home/homesemlogin.html")


def sobre(request):
    return render(request, "informacoes/sobre.html")


def custom_login(request):
    redirect_to = request.POST.get("next") or request.GET.get("next")
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, "Login realizado com sucesso!")
            if redirect_to:
                return redirect(redirect_to)
            else:
                return redirect("home")
        else:
            messages.error(request, "Usuário ou senha inválidos.")
            return redirect("login")

    return render(request, "registro/login.html", {"redirect_to": redirect_to})


@login_required
def cadastro(request):
    if request.user.nivel_permissao == "CLI":
        messages.error(request, "Sem permissão para essa página.")
        return redirect("home")

    if request.user.nivel_permissao == "ADM":
        FormUser = FormUserADM
    else:
        FormUser = ClienteForm

    form = FormUser()

    if request.method == "POST":
        form = FormUser(request.POST)

        if form.is_valid():
            user = form.save()
            messages.success(request, f"Usuário '{user.username}' Cadastrado!")
            return redirect("cadastro")
        else:
            for field in form:
                for error in field.errors:
                    messages.error(request, f"Erro em {field.label}: {error}")

            for error in form.non_field_errors():
                messages.error(request, error)

    return render(request, "registro/cadastro.html", {"form": form})


@login_required
def arquivos(request):
    context = {}
    user = request.user
    context["arquivos"] = arquivos_por_permissao(user)
    if request.method == "POST":
        if "dar_acesso" in request.POST:
            user_id = request.POST.get("usuario_id")
            user_name = request.POST.get("usuario_nome")
            arquivo_id = request.POST.get("arquivo_id")
            if not user_id or not user_name:
                messages.error(request, "Usuario não Reconhecido")
            else:
                usuario = CustomUser.objects.get(id=user_id)
                arquivo = IPFSFile.objects.get(id=arquivo_id)
                dar_acesso(arquivo, usuario)
                messages.success(request, "Usuario com acesso")
                return redirect("arquivos")
    return render(request, "arquivos/arquivos.html", context)


@login_required
def upload(request):
    if request.user.nivel_permissao == "CLI":
        messages.error(request, "Sem permissão para essa página.")
        return redirect("home")

    if request.method == "POST":
        form = IPFSForm(request.POST, request.FILES)

        if form.is_valid():
            dono_arquivo = CustomUser.objects.get(id=form.cleaned_data["cliente_id"])
            arquivo = form.cleaned_data["arquivo"]
            arq_temp = f"/tmp/{arquivo.name}"

            with open(arq_temp, "wb+") as f:
                for chunk in arquivo.chunks():
                    f.write(chunk)

            ipfs_file = uploadipfs(arq_temp)

            if isinstance(ipfs_file, int):
                messages.error(request, f"Request deu erro no Servidor: {ipfs_file}")
            else:
                if "data" in ipfs_file:
                    dados = ipfs_file["data"]
                    id_arquivo = dados["id"]
                    nome = dados["name"]
                    cid = dados["cid"]
                    tamanho = dados["size"]
                    mime_type = dados["mime_type"]
                    arq_upload = IPFSFile.objects.create(
                        pinata_id=id_arquivo,
                        cid=cid,
                        nome_arquivo=nome,
                        tamanho_arquivo=tamanho,
                        mime_type=mime_type,
                        dono_arquivo=dono_arquivo,
                    )
                    if request.user.nivel_permissao == "FUNC":
                        dar_acesso(arquivo=arq_upload, usuario_alvo=request.user)
                    messages.success(request, "Arquivo enviado com sucesso!")
                else:
                    messages.error(request, "Resposta inesperada da API Pinata")
    else:
        form = IPFSForm()

    return render(request, "arquivos/upload.html", {"form": form})


@login_required
def user(request):
    user = request.user
    if request.method == "POST":
        if "alterar_foto" in request.POST:
            form = FotoForm(request.POST, request.FILES)
            if form.is_valid():
                foto = form.cleaned_data["arquivo"]
                fotobase64 = imagem_para_base64(foto)
                user.foto_perfil = fotobase64
                user.save()
            else:
                messages.error(request, "Formato de imagem inválido")
    else:
        form = FotoForm()
    return render(request, "user/user.html", {"form": form})


@login_required
def chat_index(request):
    """Página principal do chat"""
    return render(request, "chat/chat_index.html")


@login_required
def user_list(request):
    """Lista de usuários/conversas"""
    eu = request.user
    search_query = request.GET.get('search', '').strip()

    conversations = (
        Conversation.objects.filter(participants=eu)
        .prefetch_related("messages", "participants")
        .order_by("-updated_at")
    )

    all_users = CustomUser.objects.exclude(id=eu.id).exclude(
        nivel_permissao="CLI"
    )
    
    if search_query:
        all_users = all_users.filter(username__icontains=search_query)

    all_users = all_users.order_by("username")

    users_data = []
    for user in all_users:
        conversation = conversations.filter(participants=user).first()

        user_info = {
            "id": user.id,
            "username": user.username,
            "foto_perfil": user.foto_perfil,
            "nivel_permissao": user.nivel_permissao,
            "get_nivel_permissao_display": user.get_nivel_permissao_display(),
            "last_message": None,
            "unread_count": 0,
            "active_conversation": False,
        }

        if conversation:
            last_msg = conversation.get_last_message()
            if last_msg:
                user_info["last_message"] = last_msg
            user_info["unread_count"] = conversation.get_unread_count(eu)

        users_data.append(user_info)


    # Ordena: usuários com mensagens não lidas primeiro, depois por última atividade
    users_data.sort(
        key=lambda x: (
            -x["unread_count"],
            -(x["last_message"].created_at.timestamp() if x["last_message"] else 0),
        )
    )

    context = {
        "users": users_data,
    }

    return render(request, "chat/partials/user_list.html", context)


@login_required
def get_or_create_conversation(request, user_id):
    """Obtém ou cria uma conversa com outro usuário"""
    try:
        other_user = get_object_or_404(CustomUser, id=user_id)

        if other_user == request.user:
            return JsonResponse(
                {"error": "Não é possível iniciar conversa consigo mesmo"}, status=400
            )

        # Busca conversa existente ou cria uma nova
        conversation = (
            Conversation.objects.filter(participants=request.user)
            .filter(participants=other_user)
            .distinct()
            .first()
        )

        if not conversation:
            conversation = Conversation.objects.create()
            conversation.participants.add(request.user, other_user)

        return JsonResponse(
            {
                "conversation_id": str(conversation.id),
                "redirect_url": f"/chat/{conversation.id}/",
            }
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def load_conversation(request, conversation_id):
    """Carrega uma conversa específica (apenas carga inicial)"""
    try:        
        conversation = get_object_or_404(
            Conversation, id=conversation_id, participants=request.user
        )

        messages = conversation.messages.all().order_by("created_at")

        other_user = conversation.get_other_user(request.user)

        context = {
            "conversation": conversation,
            "messages": messages,
            "other_user": other_user,
        }

        return render(request, "chat/partials/chat_conversation.html", context)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
