from asgiref.sync import async_to_sync
from django.test import TransactionTestCase

from aegis_share.consumers import ChatConsumer
from aegis_share.models import Conversation, FileAccess

from .helpers import make_file, make_user


class ChatConsumerSecurityTests(TransactionTestCase):
    def setUp(self):
        self.user_a = make_user("chat-a", role="FUNC")
        self.user_b = make_user("chat-b", role="FUNC")
        self.intruder = make_user("chat-intruder", role="FUNC")
        self.conversation = Conversation.objects.create()
        self.conversation.participants.add(self.user_a, self.user_b)

    def _consumer_for(self, user, conversation=None):
        consumer = ChatConsumer()
        consumer.user = user
        consumer.conversation_id = (conversation or self.conversation).id
        return consumer

    def test_participant_is_authorized(self):
        consumer = self._consumer_for(self.user_a)
        self.assertTrue(async_to_sync(consumer.user_belongs_to_conversation)())

    def test_non_participant_is_rejected(self):
        consumer = self._consumer_for(self.intruder)
        self.assertFalse(async_to_sync(consumer.user_belongs_to_conversation)())
        self.assertIsNone(async_to_sync(consumer.save_message)("nao autorizado"))

    def test_file_conversation_revalidates_document_access(self):
        owner = make_user("chat-owner")
        file = make_file(owner, cid="bafy-chat-file")
        FileAccess.objects.create(
            arquivo=file,
            user=self.user_a,
            granted_by=owner,
        )
        conversation = Conversation.objects.create(file=file)
        conversation.participants.add(owner, self.user_a)

        consumer = self._consumer_for(self.user_a, conversation)
        self.assertTrue(async_to_sync(consumer.user_belongs_to_conversation)())

        FileAccess.objects.filter(arquivo=file, user=self.user_a).delete()

        self.assertFalse(async_to_sync(consumer.user_belongs_to_conversation)())
        self.assertIsNone(async_to_sync(consumer.save_message)("apos revogacao"))
