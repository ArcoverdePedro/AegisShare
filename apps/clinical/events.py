from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction


def send_after_commit(group, payload):
    """Publica somente após commit; rollback descarta o evento."""

    def send():
        layer = get_channel_layer()
        if layer is not None:
            async_to_sync(layer.group_send)(group, payload)

    transaction.on_commit(send)
