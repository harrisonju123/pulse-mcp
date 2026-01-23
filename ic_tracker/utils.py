"""Shared utilities for ic_tracker."""

from datetime import datetime, timedelta, timezone


def parse_date_range(
    days: int = 14,
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[datetime, datetime] | dict:
    """Parse date range from parameters.

    Args:
        days: Number of days to look back (used if start_date not provided).
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.

    Returns:
        Tuple of (since, until) datetimes, or error dict if validation fails.
    """
    if start_date:
        try:
            since = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            until = (
                datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if end_date
                else datetime.now(timezone.utc)
            )
            if since > until:
                return {"error": "start_date must be before end_date"}
        except ValueError as e:
            return {"error": f"Invalid date format. Expected YYYY-MM-DD: {e}"}
    else:
        if days < 1 or days > 365:
            return {"error": "days must be between 1 and 365"}
        since = datetime.now(timezone.utc) - timedelta(days=days)
        until = datetime.now(timezone.utc)

    return since, until
