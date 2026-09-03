from django.db.utils import OperationalError, ProgrammingError


def notifications_context(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"unread_notifications_count": 0}

    try:
        count = request.user.notifications.filter(read_at__isnull=True).count()
    except (OperationalError, ProgrammingError):
        # Permite renderizar setup/upgrade enquanto migrations ainda estao sendo aplicadas.
        count = 0
    return {"unread_notifications_count": count}
