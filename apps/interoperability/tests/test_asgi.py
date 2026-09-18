from django.test import SimpleTestCase

from ..asgi import bounded_inbox
from ..lab_inbox import MAX_BODY_BYTES


class InboxAsgiTests(SimpleTestCase):
    async def test_excess_is_rejected_before_downstream_accepts_chunk(self):
        accepted, responses = [], []
        messages = iter(
            [
                {"type": "http.request", "body": b"x" * MAX_BODY_BYTES},
                {"type": "http.request", "body": b"x"},
            ]
        )

        async def receive():
            return next(messages)

        async def send(message):
            responses.append(message)

        async def app(scope, receive, send):
            accepted.append(await receive())
            accepted.append(await receive())

        await bounded_inbox(
            app, {"path": "/interop/laboratorio/receber/", "method": "POST"}, receive, send
        )
        self.assertEqual(len(accepted), 1)
        self.assertEqual(responses[0]["status"], 413)
        self.assertIn((b"cache-control", b"private, no-store"), responses[0]["headers"])
