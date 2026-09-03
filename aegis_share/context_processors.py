def notifications_context(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"unread_notifications_count": 0}

    try:
        count = request.user.notifications.filter(read_at__isnull=True).count()
    except Exception:
        # Mantem templates renderizaveis antes da migration inicial da feature.
        count = 0
    return {"unread_notifications_count": count}
