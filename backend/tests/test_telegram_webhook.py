from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.api.deps import get_conversation_service
from app.core.enums import ChannelType
from app.main import app, settings
from app.schemas.messages import ProcessResult
from app.services.webhook_service import WebhookService


class FakeConversationService:
    def __init__(self) -> None:
        self.received_messages = []

    async def handle_inbound(self, inbound_message):
        self.received_messages.append(inbound_message)
        return ProcessResult(
            processed_messages=1,
            outbound_messages=["Welcome to the bot"],
        )


class TelegramWebhookFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake_service = FakeConversationService()
        app.dependency_overrides[get_conversation_service] = lambda: self.fake_service
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()

    def test_normalize_telegram_update_maps_chat_and_text_correctly(self) -> None:
        payload = {
            "message": {
                "message_id": 101,
                "text": "Hi, I need bridal makeup",
                "chat": {
                    "id": 987654321,
                    "first_name": "Anita",
                    "last_name": "Sharma",
                },
            }
        }

        normalized_messages = WebhookService.normalize_telegram_update("default", payload)

        self.assertEqual(len(normalized_messages), 1)
        normalized = normalized_messages[0]
        self.assertEqual(normalized.vendor_slug, "default")
        self.assertEqual(normalized.channel, ChannelType.TELEGRAM)
        self.assertEqual(normalized.external_user_id, "987654321")
        self.assertEqual(normalized.telegram_chat_id, "987654321")
        self.assertEqual(normalized.display_name, "Anita Sharma")
        self.assertEqual(normalized.text, "Hi, I need bridal makeup")

    def test_telegram_webhook_route_processes_normalized_message(self) -> None:
        payload = {
            "message": {
                "message_id": 202,
                "text": "Hello",
                "chat": {
                    "id": 123456789,
                    "first_name": "Riya",
                    "last_name": "Singh",
                },
            }
        }

        response = self.client.post(f"{settings.api_prefix}/webhooks/telegram/default", json=payload)

        self.assertEqual(response.status_code, 200)
        response_json = response.json()
        self.assertEqual(response_json["processed"], 1)
        self.assertEqual(response_json["results"][0]["processed_messages"], 1)
        self.assertEqual(response_json["results"][0]["outbound_messages"], ["Welcome to the bot"])

        self.assertEqual(len(self.fake_service.received_messages), 1)
        inbound_message = self.fake_service.received_messages[0]
        self.assertEqual(inbound_message.vendor_slug, "default")
        self.assertEqual(inbound_message.channel, ChannelType.TELEGRAM)
        self.assertEqual(inbound_message.external_user_id, "123456789")
        self.assertEqual(inbound_message.telegram_chat_id, "123456789")
        self.assertEqual(inbound_message.display_name, "Riya Singh")
        self.assertEqual(inbound_message.text, "Hello")


if __name__ == "__main__":
    unittest.main()
