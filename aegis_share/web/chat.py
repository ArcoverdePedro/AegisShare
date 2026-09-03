from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from aegis_share.models import Conversation, CustomUser


def _chat_users(user):
    qs = CustomUser.objects.exclude(id=user.id).filter(is_active=True)
    if user.is_client():
        qs = qs.exclude(nivel_permissao="CLI")
    return qs.order_by("username")


@login_required
def chat_index(request):
    conversations = (
        Conversation.objects.filter(participants=request.user)
        .prefetch_related("participants")
        .annotate(
            unread_count=Count(
                "messages",
                filter=Q(messages__is_read=False) & ~Q(messages__sender=request.user),
            ),
            last_message_time=Max("messages__created_at"),
        )
        .order_by("-last_message_time", "-updated_at")
    )
    return render(
        request,
        "chat/chat_index.html",
        {"users": _chat_users(request.user), "conversations": conversations},
    )


@login_required
def user_list(request):
    search = request.GET.get("search", "").strip()
    users = _chat_users(request.user)
    if search:
        users = users.filter(username__icontains=search)

    conversations = {
        str(other.id): conversation
        for conversation in Conversation.objects.filter(participants=request.user)
        .prefetch_related("participants", "messages__sender")
        for other in conversation.participants.all()
        if other.id != request.user.id
    }

    users_data = []
    for other in users[:100]:
        conversation = conversations.get(str(other.id))
        last_message = conversation.get_last_message() if conversation else None
        users_data.append(
            {
                "id": other.id,
                "username": other.username,
                "foto_perfil": other.foto_perfil,
                "nivel_permissao": other.nivel_permissao,
                "get_nivel_permissao_display": other.get_nivel_permissao_display(),
                "last_message": last_message,
                "unread_count": conversation.get_unread_count(request.user) if conversation else 0,
            }
        )

    users_data.sort(
        key=lambda item: (
            -item["unread_count"],
            -(item["last_message"].created_at.timestamp() if item["last_message"] else 0),
        )
    )
    return render(request, "chat/partials/user_list.html", {"users": users_data})


@login_required
def get_or_create_conversation(request, user_id):
    other_user = get_object_or_404(_chat_users(request.user), id=user_id)
    conversation = (
        Conversation.objects.filter(participants=request.user)
        .filter(participants=other_user)
        .filter(file__isnull=True)
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


@login_required
def load_conversation(request, conversation_id):
    conversation = get_object_or_404(
        Conversation.objects.prefetch_related("participants"),
        id=conversation_id,
        participants=request.user,
    )
    conversation.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
    messages = conversation.messages.select_related("sender").order_by("created_at")
    return render(
        request,
        "chat/partials/chat_conversation.html",
        {
            "conversation": conversation,
            "messages": messages,
            "other_user": conversation.get_other_user(request.user),
        },
    )
