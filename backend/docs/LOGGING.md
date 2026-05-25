# Logging System

The Beauty Parlour Chatbot uses a comprehensive logging system to track application behavior, debug issues, and monitor performance.

## Overview

The logging system provides:

- **Console Logging**: Real-time log output to stdout (colored in development)
- **File Logging**: Persistent logs with automatic rotation
- **Error Tracking**: Separate error log for quick issue identification
- **Configurable Levels**: Different verbosity for development vs production

## Log Files

All logs are stored in the `logs/` directory (automatically created):

| File | Description | Log Level |
|------|-------------|-----------|
| `logs/app.log` | All application logs | DEBUG (dev) / INFO (prod) |
| `logs/error.log` | Error-only logs with detailed context | ERROR+ |

### Log Rotation

- Maximum file size: **10 MB**
- Backup count: **5 files** per log type
- Old logs are automatically rotated and compressed

## Log Format

### Standard Format
```
2026-04-09 14:32:15 | INFO     | app.main | Application started: Beauty Parlour Chatbot (env=development, debug=True)
```

### Error Format (includes module, function, and line number)
```
2026-04-09 14:32:20 | ERROR    | app.api.router | router.py:process_booking:45 | Failed to process booking: Invalid date format
```

## Viewing Logs

### Method 1: Using the Batch Script (Windows)
```bash
# View recent 50 lines
view_logs.bat

# View last 100 lines
view_logs.bat --tail 100

# View only errors
view_logs.bat --errors

# Follow logs in real-time
view_logs.bat --follow
```

### Method 2: Using Python Module
```bash
cd Beauty_Parlour_chatbot-

# View recent logs
python -m app.utils.log_viewer

# View last 100 lines
python -m app.utils.log_viewer --tail 100

# View only errors
python -m app.utils.log_viewer --errors

# Follow in real-time
python -m app.utils.log_viewer --follow
```

### Method 3: Direct File Access
```bash
# Windows PowerShell
Get-Content logs/app.log -Tail 50
Get-Content logs/error.log -Tail 50 -Wait

# Git Bash / WSL
tail -f logs/app.log
tail -f logs/error.log
```

## Using the Logger in Code

Import and use the logger in any module:

```python
import logging

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Usage examples
logger.debug("Detailed debug information for development")
logger.info("Booking created successfully for user_id=%s", user_id)
logger.warning("Rate limit approaching for API key: %s", api_key)
logger.error("Failed to connect to database: %s", error)
logger.exception("Exception occurred")  # Use in except blocks (includes traceback)
```

## Log Levels

| Level | When to Use | Environment |
|-------|-------------|-------------|
| `DEBUG` | Detailed diagnostic information | Development only |
| `INFO` | Normal operational events | Development & Production |
| `WARNING` | Potential issues or degraded performance | Development & Production |
| `ERROR` | Errors that prevent operations | Development & Production |
| `CRITICAL` | System failures requiring immediate attention | Development & Production |

## Configuration

Logging is automatically configured when the FastAPI application starts in `app/main.py`:

```python
from app.core.logging_config import setup_logging

# Configure logging before anything else
setup_logging()
```

### Environment-Based Configuration

- **Development** (`debug=True`): DEBUG level logs
- **Production** (`debug=False`): INFO level logs

Third-party library log levels are adjusted to reduce noise:
- `uvicorn.access`: WARNING+
- `sqlalchemy.engine`: WARNING+ (INFO+ in debug mode)
- `httpx`: WARNING+

## Best Practices

1. **Use appropriate log levels**: Don't log everything as ERROR
2. **Include context**: Add relevant IDs, usernames, or parameters
3. **Use lazy formatting**: Pass arguments to logger, not pre-formatted strings
   ```python
   # ✅ Good
   logger.info("User %s booked appointment %s", user_id, appointment_id)
   
   # ❌ Bad
   logger.info(f"User {user_id} booked appointment {appointment_id}")
   ```
4. **Log exceptions properly**: Use `logger.exception()` in except blocks
5. **Don't log sensitive data**: Never log passwords, tokens, or PII

## Troubleshooting

### Logs not appearing?
- Check if the `logs/` directory exists
- Verify the application has write permissions
- Ensure logging is initialized: `setup_logging()` is called in `app/main.py`

### Log files too large?
- Check rotation settings in `app/core/logging_config.py`
- Manually delete old rotated logs if needed

### Need more verbose logs?
- Set `DEBUG=True` in your `.env` file
- Restart the application to apply changes

## Monitoring in Production

For production deployments, consider:
- **Log aggregation**: Ship logs to services like Datadog, ELK Stack, or CloudWatch
- **Alerting**: Set up alerts for ERROR and CRITICAL logs
- **Log analysis**: Use tools like Graylog or Splunk for advanced search
