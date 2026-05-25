require('dotenv').config();

const express = require('express');
const cors = require('cors');
const path = require('path');

const { pool, init: initDb } = require('./db');
const { rateLimit } = require('./redis');
const {
  sendInquiryNotifications,
  sendCallbackNotifications,
  sendApplicationNotifications,
} = require('./email');

const app = express();
const PORT = parseInt(process.env.PORT || '3000', 10);
const BUSINESS_EMAIL = process.env.BUSINESS_EMAIL || process.env.GMAIL_USER || 'farburgh@gmail.com';

const BASE_STUDENTS = parseInt(process.env.BASE_STUDENTS || '1200', 10);
const BASE_COUNTRIES = parseInt(process.env.BASE_COUNTRIES || '6', 10);
const BASE_UNIVERSITIES = parseInt(process.env.BASE_UNIVERSITIES || '40', 10);
const BASE_EXPERIENCE = parseInt(process.env.BASE_EXPERIENCE || '12', 10);

app.set('trust proxy', 1);
app.use(cors());
app.use(express.json({ limit: '50kb' }));
app.use(express.static(path.join(__dirname)));

const getIp = (req) => req.ip || req.connection?.remoteAddress || 'unknown';
const bad = (res, msg) => res.status(400).json({ ok: false, error: msg });
const isEmail = (s) => typeof s === 'string' && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s);

// ---------- Public config ----------
app.get('/api/config', (req, res) => {
  res.json({
    ok: true,
    businessEmail: BUSINESS_EMAIL,
  });
});

// ---------- Inquiry ----------
app.post('/api/inquiries', async (req, res) => {
  try {
    const { name, email, message } = req.body || {};
    if (!name || !email || !message) return bad(res, 'Missing required fields');
    if (!isEmail(email)) return bad(res, 'Invalid email address');
    if (name.length > 200 || message.length > 5000) return bad(res, 'Field too long');

    const ip = getIp(req);
    const ua = req.get('user-agent') || null;

    const rl = await rateLimit(`inquiry:${ip}`, 5, 300);
    if (!rl.allowed) return res.status(429).json({ ok: false, error: 'Too many requests, please slow down.' });

    const result = await pool.query(
      'INSERT INTO inquiries (name, email, message, ip, user_agent) VALUES ($1,$2,$3,$4,$5) RETURNING id',
      [name.trim(), email.trim(), message.trim(), ip, ua]
    );

    sendInquiryNotifications({ name, email, message }).catch((err) =>
      console.error('[email] inquiry send failed:', err.message)
    );

    res.json({ ok: true, id: result.rows[0].id });
  } catch (err) {
    console.error('[inquiries] error:', err);
    res.status(500).json({ ok: false, error: 'Server error' });
  }
});

// ---------- Callback ----------
app.post('/api/callback', async (req, res) => {
  try {
    const { name, phone, email, preferredTime } = req.body || {};
    if (!name || !phone) return bad(res, 'Name and phone are required');
    if (name.length > 200 || phone.length > 30) return bad(res, 'Field too long');
    if (email && !isEmail(email)) return bad(res, 'Invalid email address');

    const ip = getIp(req);
    const ua = req.get('user-agent') || null;

    const rl = await rateLimit(`callback:${ip}`, 3, 600);
    if (!rl.allowed) return res.status(429).json({ ok: false, error: 'Too many requests, please slow down.' });

    const result = await pool.query(
      'INSERT INTO callbacks (name, phone, email, preferred_time, ip, user_agent) VALUES ($1,$2,$3,$4,$5,$6) RETURNING id',
      [name.trim(), phone.trim(), email ? email.trim() : null, preferredTime || null, ip, ua]
    );

    sendCallbackNotifications({ name, phone, email, preferredTime }).catch((err) =>
      console.error('[email] callback send failed:', err.message)
    );

    res.json({ ok: true, id: result.rows[0].id });
  } catch (err) {
    console.error('[callback] error:', err);
    res.status(500).json({ ok: false, error: 'Server error' });
  }
});

// ---------- Application ----------
app.post('/api/applications', async (req, res) => {
  try {
    const { name, email, phone, education, course, country, intake, message } = req.body || {};
    if (!name || !email || !phone) return bad(res, 'Name, email, and phone are required');
    if (!isEmail(email)) return bad(res, 'Invalid email address');

    const ip = getIp(req);
    const ua = req.get('user-agent') || null;

    const rl = await rateLimit(`app:${ip}`, 3, 600);
    if (!rl.allowed) return res.status(429).json({ ok: false, error: 'Too many requests, please slow down.' });

    const result = await pool.query(
      `INSERT INTO applications (name, email, phone, education, course, country, intake, message, ip, user_agent)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) RETURNING id`,
      [
        name.trim(),
        email.trim(),
        phone.trim(),
        education || null,
        course || null,
        country || null,
        intake || null,
        message || null,
        ip,
        ua,
      ]
    );

    sendApplicationNotifications({ name, email, phone, education, course, country, intake, message }).catch((err) =>
      console.error('[email] application send failed:', err.message)
    );

    res.json({ ok: true, id: result.rows[0].id });
  } catch (err) {
    console.error('[applications] error:', err);
    res.status(500).json({ ok: false, error: 'Server error' });
  }
});

// ---------- QR generation log (fire-and-forget) ----------
app.post('/api/qr/log', async (req, res) => {
  const { url } = req.body || {};
  if (!url || typeof url !== 'string' || url.length > 2000) return bad(res, 'URL required');
  const ip = getIp(req);
  pool
    .query('INSERT INTO qr_logs (url, ip) VALUES ($1, $2)', [url, ip])
    .catch((err) => console.error('[qr-log] insert failed:', err.message));
  res.json({ ok: true });
});

// ---------- Live stats ----------
app.get('/api/stats', async (req, res) => {
  try {
    const { rows } = await pool.query(`
      SELECT
        (SELECT COUNT(*) FROM applications) AS apps,
        (SELECT COUNT(DISTINCT country) FROM applications WHERE country IS NOT NULL AND country <> '') AS countries
    `);
    const r = rows[0] || { apps: 0, countries: 0 };
    const apps = parseInt(r.apps, 10) || 0;
    const distinctCountries = parseInt(r.countries, 10) || 0;
    res.json({
      ok: true,
      students: BASE_STUDENTS + apps,
      countries: Math.max(BASE_COUNTRIES, distinctCountries),
      universities: BASE_UNIVERSITIES,
      experience: BASE_EXPERIENCE,
    });
  } catch (err) {
    console.error('[stats] error:', err.message);
    res.json({
      ok: false,
      students: BASE_STUDENTS,
      countries: BASE_COUNTRIES,
      universities: BASE_UNIVERSITIES,
      experience: BASE_EXPERIENCE,
    });
  }
});

// ---------- Health ----------
app.get('/api/health', async (req, res) => {
  let dbOk = false;
  try {
    await pool.query('SELECT 1');
    dbOk = true;
  } catch {}
  res.json({ ok: true, db: dbOk });
});

// ---------- Boot ----------
async function start() {
  try {
    await initDb();
  } catch (err) {
    console.error('[fatal] db init failed:', err.message);
    console.error('Is Postgres running? Try: docker compose up -d');
    process.exit(1);
  }
  app.listen(PORT, () => {
    console.log(`[server] http://localhost:${PORT}`);
    console.log(`[server] business inbox: ${BUSINESS_EMAIL}`);
  });
}

start();
