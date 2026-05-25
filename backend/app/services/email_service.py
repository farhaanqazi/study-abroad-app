from __future__ import annotations

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.core.config import Settings
from app.utils.logger import app_logger


class EmailService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.smtp_host = settings.email_smtp_host
        self.smtp_port = settings.email_smtp_port
        self.smtp_user = settings.email_smtp_user
        self.smtp_password = settings.email_smtp_password
        self.from_email = settings.email_from
        self.enabled = self.smtp_host and self.smtp_user and self.smtp_password

    async def send_appointment_confirmation(
        self,
        to_email: str,
        customer_name: str,
        vendor_name: str,
        service_name: str,
        appointment_date: str,
        appointment_time: str,
        booking_reference: str,
    ) -> bool:
        """Send booking confirmation email to the customer."""
        if not self.enabled:
            app_logger.info("Email service not configured, skipping customer confirmation email.")
            return False

        subject = f"Booking Confirmed: {service_name} at {vendor_name}"
        body = f"""
        <html>
            <body style="font-family: sans-serif; line-height: 1.6;">
                <h2 style="color: #333;">Booking Confirmation</h2>
                <p>Hello {customer_name},</p>
                <p>Your appointment has been successfully confirmed.</p>
                <div style="background-color: #f4f4f4; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p><strong>Service:</strong> {service_name}</p>
                    <p><strong>Date:</strong> {appointment_date}</p>
                    <p><strong>Time:</strong> {appointment_time}</p>
                    <p><strong>Booking Reference:</strong> {booking_reference}</p>
                    <p><strong>Vendor:</strong> {vendor_name}</p>
                </div>
                <p>If you need to reschedule or cancel, please contact us or reply to this message.</p>
                <p>Thank you!</p>
            </body>
        </html>
        """
        return await self._send_email(to_email, subject, body)

    async def send_owner_notification(
        self,
        owner_email: str,
        vendor_name: str,
        customer_email: str,
        service_name: str,
        appointment_date: str,
        appointment_time: str,
        booking_reference: str,
    ) -> bool:
        """Send new booking notification email to the vendor owner."""
        if not self.enabled:
            app_logger.info("Email service not configured, skipping owner notification email.")
            return False

        subject = f"New Booking: {service_name} at {vendor_name}"
        body = f"""
        <html>
            <body style="font-family: sans-serif; line-height: 1.6;">
                <h2 style="color: #333;">New Appointment Booking</h2>
                <p>A new appointment has been booked.</p>
                <div style="background-color: #f4f4f4; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p><strong>Service:</strong> {service_name}</p>
                    <p><strong>Date:</strong> {appointment_date}</p>
                    <p><strong>Time:</strong> {appointment_time}</p>
                    <p><strong>Booking Reference:</strong> {booking_reference}</p>
                    <p><strong>Customer Email:</strong> {customer_email}</p>
                    <p><strong>Vendor:</strong> {vendor_name}</p>
                </div>
            </body>
        </html>
        """
        return await self._send_email(owner_email, subject, body)

    async def notify_lead(
        self,
        *,
        lead_type: str,
        vendor_name: str,
        business_email: str | None,
        details: dict[str, object],
        student_email: str | None = None,
        student_name: str | None = None,
    ) -> None:
        """Fire-and-forget lead notifications.

        Emails the business inbox with the captured lead, and (if we have the
        student's email) sends them a short acknowledgement. No-ops cleanly
        when SMTP is unconfigured — this replaces Horizon's "dry-run" mode.
        """
        if not self.enabled:
            app_logger.info(
                "Email service not configured, skipping lead notifications.",
                event="lead_email_skipped",
                lead_type=lead_type,
            )
            return

        rows = "".join(
            f'<p><strong>{key}:</strong> {value}</p>'
            for key, value in details.items()
            if value not in (None, "")
        )
        if business_email:
            subject = f"New {lead_type} lead — {vendor_name}"
            body = f"""
            <html><body style="font-family: sans-serif; line-height: 1.6;">
                <h2 style="color: #333;">New {lead_type} lead</h2>
                <p>A new {lead_type} was submitted for <strong>{vendor_name}</strong>.</p>
                <div style="background-color: #f4f4f4; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    {rows}
                </div>
            </body></html>
            """
            await self._send_email(business_email, subject, body)

        if student_email:
            greeting = f"Hello {student_name}," if student_name else "Hello,"
            ack_subject = f"We received your {lead_type} — {vendor_name}"
            ack_body = f"""
            <html><body style="font-family: sans-serif; line-height: 1.6;">
                <p>{greeting}</p>
                <p>Thanks for reaching out to <strong>{vendor_name}</strong>. We've received
                your {lead_type} and a counsellor will get back to you shortly.</p>
            </body></html>
            """
            await self._send_email(student_email, ack_subject, ack_body)

    async def _send_email(self, to_email: str, subject: str, body: str) -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_email or self.smtp_user
            msg["To"] = to_email
            msg.attach(MIMEText(body, "html"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            app_logger.info(f"Email sent successfully to {to_email}")
            return True
        except Exception as e:
            app_logger.error(f"Failed to send email to {to_email}: {e}")
            return False
