from __future__ import annotations

import asyncio
from typing import List

import httpx

from app.core.config import Settings
from app.db.models.vendor import VendorChannel
from app.messaging.base import DeliveryResult, MessagingTransport
from app.schemas.messages import OutboundInstruction
from app.utils.logger import app_logger


class TelegramTransport(MessagingTransport):
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http_client = http_client

    async def send_instruction(
        self,
        channel_config: VendorChannel,
        destination: str,
        instruction: OutboundInstruction,
    ) -> List[DeliveryResult]:
        """
        Send instruction via Telegram.
        
        Handles errors gracefully - logs failures and returns partial results
        instead of crashing the entire webhook handler.
        """
        token = (channel_config.provider_config or {}).get("bot_token")
        if not token:
            app_logger.error(
                "Telegram bot token not configured for vendor channel",
                event="telegram_send_error",
                channel_id=str(channel_config.id),
            )
            return []

        deliveries: List[DeliveryResult] = []
        
        # Send text message (with optional inline keyboard buttons)
        if instruction.text:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            # Telegram uses single-asterisk *text* for bold in Markdown mode
            payload: dict = {
                "chat_id": destination,
                "text": instruction.text,
                "parse_mode": "Markdown",
            }

            # Add inline keyboard buttons if present
            if instruction.buttons:
                app_logger.info(f"Telegram sending message with {len(instruction.buttons)} buttons: {[btn['label'] for btn in instruction.buttons]}")
                # One button per row — full width, nothing gets clipped on mobile
                keyboard = [
                    [{"text": btn["label"], "callback_data": btn["callback"]}]
                    for btn in instruction.buttons
                ]

                payload["reply_markup"] = {"inline_keyboard": keyboard}
                app_logger.debug(f"Telegram button payload: {payload['reply_markup']}")
            
            try:
                response = await self.http_client.post(url, json=payload, timeout=10.0)
                response.raise_for_status()
                data = response.json()

                # Check Telegram API response status (even 200 OK can contain errors)
                if not data.get("ok", False):
                    error_desc = data.get("description", "Unknown error")
                    app_logger.error(f"Telegram API error: {error_desc}")
                else:
                    message_id = data.get("result", {}).get("message_id")
                    if not message_id:
                        app_logger.error(f"Telegram API didn't return message_id in response: {data}")
                    else:
                        deliveries.append(
                            DeliveryResult(
                                provider_message_id=str(message_id),
                                text=instruction.text,
                                payload=payload,
                            )
                        )
            except httpx.HTTPStatusError as e:
                app_logger.error(f"Telegram API error (status {e.response.status_code}): {e.response.text[:200]}")
            except httpx.TimeoutException as e:
                app_logger.error(f"Telegram API timeout: {e}")
            except Exception as e:
                app_logger.error(f"Unexpected error sending Telegram message: {e}")

        # Send media (photos) - use gather for parallel sends
        if instruction.media_urls:
            send_tasks = []
            for media_url in instruction.media_urls:
                send_tasks.append(self._send_photo(token, destination, media_url))
            
            # Send photos in parallel
            results = await asyncio.gather(*send_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, DeliveryResult):
                    deliveries.append(result)
                elif isinstance(result, Exception):
                    app_logger.error(f"Failed to send photo: {result}")
        
        return deliveries

    async def _send_photo(
        self,
        token: str,
        destination: str,
        media_url: str,
    ) -> DeliveryResult | None:
        """Send a single photo, with error handling."""
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        payload = {"chat_id": destination, "photo": media_url}
        try:
            response = await self.http_client.post(url, json=payload, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            
            # Check Telegram API response status (even 200 OK can contain errors)
            if not data.get("ok", False):
                error_desc = data.get("description", "Unknown error")
                app_logger.error(f"Telegram photo API error: {error_desc}")
                return None
            
            message_id = data.get("result", {}).get("message_id")
            if not message_id:
                app_logger.error(f"Telegram photo API didn't return message_id in response: {data}")
                return None
            
            return DeliveryResult(
                provider_message_id=str(message_id),
                text=f"[photo] {media_url}",
                payload=payload,
            )
        except httpx.HTTPStatusError as e:
            app_logger.error(f"Telegram photo error (status {e.response.status_code}): {e.response.text[:200]}")
        except httpx.TimeoutException as e:
            app_logger.error(f"Telegram photo timeout: {e}")
        except Exception as e:
            app_logger.error(f"Unexpected error sending photo: {e}")
        return None
