"""
Log viewer utility for the Beauty Parlour Chatbot application.

Usage:
    python -m app.utils.log_viewer          # Show recent logs
    python -m app.utils.log_viewer --tail 100  # Show last 100 lines
    python -m app.utils.log_viewer --errors     # Show only errors
    python -m app.utils.log_viewer --follow     # Follow logs in real-time
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def get_log_file_path(error_log: bool = False) -> Path:
    """Get the path to the log file."""
    log_dir = Path("logs")
    if not log_dir.exists():
        print(f"Error: Logs directory '{log_dir}' does not exist.")
        sys.exit(1)

    filename = "error.log" if error_log else "app.log"
    log_file = log_dir / filename

    if not log_file.exists():
        print(f"Error: Log file '{log_file}' does not exist. Start the application first.")
        sys.exit(1)

    return log_file


def tail_log(lines: int = 50, error_only: bool = False) -> None:
    """Display the last N lines of the log file."""
    log_file = get_log_file_path(error_log=error_only)

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:]

        print(f"\n{'='*80}")
        print(f"Recent logs from {log_file.name} (last {lines} lines)")
        print(f"{'='*80}\n")

        for line in recent_lines:
            print(line, end="")

        print(f"\n{'='*80}\n")

    except Exception as e:
        print(f"Error reading log file: {e}")
        sys.exit(1)


def follow_log(error_only: bool = False) -> None:
    """Follow the log file in real-time (like tail -f)."""
    log_file = get_log_file_path(error_log=error_only)

    print(f"\nFollowing {log_file.name} (Press Ctrl+C to stop)...\n")

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            # Move to the end of the file
            f.seek(0, 2)

            while True:
                line = f.readline()
                if line:
                    print(line, end="")
                else:
                    time.sleep(0.1)  # Wait for new content
    except KeyboardInterrupt:
        print("\n\nStopped following logs.")
    except Exception as e:
        print(f"Error reading log file: {e}")
        sys.exit(1)


def main() -> None:
    """Main entry point for the log viewer."""
    parser = argparse.ArgumentParser(description="View application logs")
    parser.add_argument(
        "--tail",
        type=int,
        default=50,
        help="Number of lines to show from the end (default: 50)",
    )
    parser.add_argument(
        "--errors",
        action="store_true",
        help="Show only error logs",
    )
    parser.add_argument(
        "--follow",
        action="store_true",
        help="Follow logs in real-time",
    )

    args = parser.parse_args()

    if args.follow:
        follow_log(error_only=args.errors)
    else:
        tail_log(lines=args.tail, error_only=args.errors)


if __name__ == "__main__":
    main()
