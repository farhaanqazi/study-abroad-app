from __future__ import annotations

from typing import Any

from app.core.enums import ChannelType
from app.schemas.messages import NormalizedInboundMessage
from app.utils.logger import app_logger


class WebhookService:
    @staticmethod
    def normalize_telegram_update(vendor_slug: str, payload: dict[str, Any]) -> list[NormalizedInboundMessage]:
        messages: list[NormalizedInboundMessage] = []

        # Handle regular text messages
        message = payload.get("message") or payload.get("edited_message")
        if message:
            text = message.get("text") or message.get("caption")
            if text:
                chat = message.get("chat", {})
                display_name = " ".join(filter(None, [chat.get("first_name"), chat.get("last_name")])).strip() or None
                external_user_id = str(chat.get("id"))
                messages.append(
                    NormalizedInboundMessage(
                        vendor_slug=vendor_slug,
                        channel=ChannelType.TELEGRAM,
                        external_user_id=external_user_id,
                        text=text,
                        raw_payload=payload,
                        provider_message_id=str(message.get("message_id")),
                        display_name=display_name,
                        telegram_chat_id=external_user_id,
                    )
                )
        
        # Handle inline button callback queries
        callback_query = payload.get("callback_query")
        if callback_query:
            callback_data = callback_query.get("data", "")
            chat = callback_query.get("message", {}).get("chat", {})
            external_user_id = str(chat.get("id"))
            display_name = " ".join(filter(None, [chat.get("first_name"), chat.get("last_name")])).strip() or None
            
            messages.append(
                NormalizedInboundMessage(
                    vendor_slug=vendor_slug,
                    channel=ChannelType.TELEGRAM,
                    external_user_id=external_user_id,
                    text=callback_data,  # Button callback data becomes the message text
                    raw_payload=payload,
                    provider_message_id=str(callback_query.get("id")),
                    display_name=display_name,
                    telegram_chat_id=external_user_id,
                )
            )
        
        return messages

    @staticmethod
    def normalize_whatsapp_update(vendor_slug: str, payload: dict[str, Any]) -> list[NormalizedInboundMessage]:
        normalized_messages: list[NormalizedInboundMessage] = []
        entries = payload.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                contacts = {contact.get("wa_id"): contact for contact in value.get("contacts", [])}
                for message in value.get("messages", []):
                    text = WebhookService._extract_whatsapp_text(message)
                    if not text:
                        continue
                    external_user_id = message.get("from")
                    contact = contacts.get(external_user_id, {})
                    normalized_messages.append(
                        NormalizedInboundMessage(
                            vendor_slug=vendor_slug,
                            channel=ChannelType.WHATSAPP,
                            external_user_id=external_user_id,
                            text=text,
                            raw_payload=payload,
                            provider_message_id=message.get("id"),
                            display_name=contact.get("profile", {}).get("name"),
                            phone_number=external_user_id,
                        )
                    )
        return normalized_messages

    @staticmethod
    def _extract_whatsapp_text(message: dict[str, Any]) -> str | None:
        message_type = message.get("type")
        if message_type == "text":
            return message.get("text", {}).get("body")
        if message_type == "button":
            return message.get("button", {}).get("text")
        if message_type == "interactive":
            interactive = message.get("interactive", {})
            button_reply = interactive.get("button_reply", {})
            list_reply = interactive.get("list_reply", {})
            return button_reply.get("title") or list_reply.get("title")
        return None
