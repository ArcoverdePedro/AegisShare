from asgiref.sync import async_to_sync
from django.test import TransactionTestCase

from aegis_share.consumers import ChatConsumer
from aegis_share.models import Conversation

from .helpers import make_user


class ChatConsumerSecurityTests(TransactionTestCase):
    def setUp(self):
        self.user_a = make_user("chat-a", role="FUNC")
        self.user_b = make_user("chat-b", role="FUNC")
        self.intruder = make_user("chat-intruder", role="FUNC")
        self.conversation = Conversation.objects.create()
        self.conversation.participants.add(self.user_a, self.user_b)

    def _consumer_for(self, user):
        consumer = ChatConsumer()
        consumer.user = user
        consumer.conversation_id = self.conversation.id
        return consumer

    def test_participant_is_authorized(self):
        consumer = self._consumer_for(self.user_a)
        self.assertTrue(async_to_sync(consumer.user_belongs_to_conversation)())

    def test_non_participant_is_rejected(self):
        consumer = self._consumer_for(self.intruder)
        self.assertFalse(async_to_sync(consumer.user_belongs_to_conversation)())
        self.assertIsNone(async_to_sync(consumer.save_message)("nao autorizado"))
