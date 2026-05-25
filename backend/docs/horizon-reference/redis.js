const Redis = require('ioredis');

const client = new Redis(process.env.REDIS_URL || 'redis://localhost:6379', {
  maxRetriesPerRequest: 3,
  enableOfflineQueue: false,
});

client.on('error', (err) => console.error('[redis] error:', err.message));
client.on('connect', () => console.log('[redis] connected'));

// Sliding-window rate limit. Returns { allowed, count, max }.
// If Redis is unavailable, fail-open so the site keeps working.
async function rateLimit(key, max, windowSec) {
  const fullKey = `rl:${key}`;
  const now = Date.now();
  const cutoff = now - windowSec * 1000;

  try {
    const pipeline = client.pipeline();
    pipeline.zremrangebyscore(fullKey, 0, cutoff);
    pipeline.zcard(fullKey);
    pipeline.zadd(fullKey, now, `${now}-${Math.random()}`);
    pipeline.expire(fullKey, windowSec);
    const results = await pipeline.exec();
    const count = results[1][1];
    return { allowed: count < max, count, max };
  } catch (err) {
    console.error('[redis] rateLimit failed, allowing request:', err.message);
    return { allowed: true, count: 0, max, degraded: true };
  }
}

module.exports = { client, rateLimit };
