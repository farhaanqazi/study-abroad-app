from __future__ import annotations

import asyncio
import logging
from typing import List

import httpx

from app.core.config import Settings
from app.db.models.vendor import VendorChannel
from app.messaging.base import DeliveryResult, MessagingTransport
from app.schemas.messages import OutboundInstruction


logger = logging.getLogger(__name__)


class WhatsAppTransport(MessagingTransport):
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
        Send instruction via WhatsApp.
        
        Handles errors gracefully - logs failures and returns partial results
        instead of crashing the entire webhook handler.
        """
        access_token = channel_config.provider_config.get("access_token") or self.settings.whatsapp_access_token
        phone_number_id = (
            channel_config.provider_config.get("phone_number_id") or self.settings.whatsapp_phone_number_id
        )
        if not access_token or not phone_number_id:
            logger.warning("WhatsApp credentials not configured")
            return []

        url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
        headers = {"Authorization": f"Bearer {access_token}"}
        deliveries: List[DeliveryResult] = []

        # Send text message
        if instruction.text:
            payload = {
                "messaging_product": "whatsapp",
                "to": destination,
                "type": "text",
                "text": {"body": instruction.text},
            }
            try:
                response = await self.http_client.post(url, headers=headers, json=payload, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                deliveries.append(
                    DeliveryResult(
                        provider_message_id=(data.get("messages") or [{}])[0].get("id"),
                        text=instruction.text,
                        payload=payload,
                    )
                )
            except httpx.HTTPStatusError as e:
                logger.error(f"WhatsApp API error (status {e.response.status_code}): {e.response.text[:200]}")
            except httpx.TimeoutException as e:
                logger.error(f"WhatsApp API timeout: {e}")
            except Exception as e:
                logger.error(f"Unexpected error sending WhatsApp message: {e}")

        # Send media (images) - use gather for parallel sends
        if instruction.media_urls:
            send_tasks = []
            for media_url in instruction.media_urls:
                send_tasks.append(self._send_image(url, headers, destination, media_url))
            
            # Send images in parallel
            results = await asyncio.gather(*send_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, DeliveryResult):
                    deliveries.append(result)
                elif isinstance(result, Exception):
                    logger.error(f"Failed to send image: {result}")
        
        return deliveries

    async def _send_image(
        self,
        url: str,
        headers: dict,
        destination: str,
        media_url: str,
    ) -> DeliveryResult | None:
        """Send a single image, with error handling."""
        payload = {
            "messaging_product": "whatsapp",
            "to": destination,
            "type": "image",
            "image": {"link": media_url},
        }
        try:
            response = await self.http_client.post(url, headers=headers, json=payload, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            return DeliveryResult(
                provider_message_id=(data.get("messages") or [{}])[0].get("id"),
                text=f"[image] {media_url}",
                payload=payload,
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"WhatsApp image error (status {e.response.status_code}): {e.response.text[:200]}")
        except httpx.TimeoutException as e:
            logger.error(f"WhatsApp image timeout: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending image: {e}")
        return None
