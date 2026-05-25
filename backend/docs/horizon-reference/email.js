const nodemailer = require('nodemailer');

const GMAIL_USER = process.env.GMAIL_USER;
const GMAIL_APP_PASSWORD = process.env.GMAIL_APP_PASSWORD;
const BUSINESS_EMAIL = process.env.BUSINESS_EMAIL || GMAIL_USER;
const FROM_NAME = process.env.FROM_NAME || 'Horizon Education';

let transporter = null;

function isPlaceholderPassword(pw) {
  if (!pw) return true;
  if (pw.toLowerCase().includes('xxxx')) return true;
  // Real Gmail App Passwords are 16 chars (sometimes shown with spaces or dashes — strip them)
  if (pw.replace(/[\s-]/g, '').length < 16) return true;
  return false;
}

function getTransporter() {
  if (transporter) return transporter;
  if (!GMAIL_USER || isPlaceholderPassword(GMAIL_APP_PASSWORD)) {
    return null;
  }
  transporter = nodemailer.createTransport({
    host: 'smtp.gmail.com',
    port: 465,
    secure: true,
    auth: { user: GMAIL_USER, pass: GMAIL_APP_PASSWORD.replace(/[\s-]/g, '') },
  });
  return transporter;
}

async function send(opts) {
  const t = getTransporter();
  if (!t) {
    console.log('[email:dry-run]', JSON.stringify({ to: opts.to, subject: opts.subject }));
    return { dryRun: true };
  }
  return t.sendMail({ from: `"${FROM_NAME}" <${GMAIL_USER}>`, ...opts });
}

async function sendInquiryNotifications({ name, email, message }) {
  const userMail = send({
    to: email,
    subject: 'We received your inquiry — Horizon Education',
    text:
`Hi ${name},

Thank you for reaching out to Horizon Education. We've received your inquiry and one of our advisors will get back to you within 24 hours.

Your message:
"${message}"

Best regards,
Horizon Education Team`,
  });

  const adminMail = send({
    to: BUSINESS_EMAIL,
    replyTo: email,
    subject: `New inquiry from ${name}`,
    text:
`New inquiry received:

Name: ${name}
Email: ${email}

Message:
${message}

— Horizon Web`,
  });

  return Promise.all([userMail, adminMail]);
}

async function sendCallbackNotifications({ name, phone, email, preferredTime }) {
  const adminMail = send({
    to: BUSINESS_EMAIL,
    replyTo: email || undefined,
    subject: `Callback request — ${name}`,
    text:
`Callback requested:

Name: ${name}
Phone: ${phone}
Email: ${email || '(not provided)'}
Preferred time: ${preferredTime || 'anytime'}

Please call back within 24 hours.

— Horizon Web`,
  });

  const sends = [adminMail];
  if (email) {
    sends.push(send({
      to: email,
      subject: 'Callback scheduled — Horizon Education',
      text:
`Hi ${name},

We've received your callback request. One of our advisors will call you on ${phone} within 24 hours${preferredTime ? ` (preferred time: ${preferredTime})` : ''}.

If you need immediate assistance, just reply to this email.

Best regards,
Horizon Education Team`,
    }));
  }

  return Promise.all(sends);
}

async function sendApplicationNotifications(app) {
  const userMail = send({
    to: app.email,
    subject: 'Application received — Horizon Education',
    text:
`Hi ${app.name},

Thank you for starting your application with Horizon Education. We've received the following details:

Course: ${app.course || '—'}
Country: ${app.country || '—'}
Intake: ${app.intake || '—'}

A dedicated advisor will reach out to you on ${app.phone} within 24 hours to discuss next steps.

Best regards,
Horizon Education Team`,
  });

  const adminMail = send({
    to: BUSINESS_EMAIL,
    replyTo: app.email,
    subject: `New application — ${app.name}`,
    text:
`New application:

Name: ${app.name}
Email: ${app.email}
Phone: ${app.phone}
Education: ${app.education || '—'}
Course: ${app.course || '—'}
Country: ${app.country || '—'}
Intake: ${app.intake || '—'}

Message:
${app.message || '(none)'}

— Horizon Web`,
  });

  return Promise.all([userMail, adminMail]);
}

module.exports = {
  sendInquiryNotifications,
  sendCallbackNotifications,
  sendApplicationNotifications,
};
