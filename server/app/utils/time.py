from datetime import date, datetime, time, timezone

END_OF_DAY = time(23, 59, 59)


def utcnow() -> datetime:
    """Shared naive-UTC clock — matches how pymongo round-trips datetimes by default."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_today() -> date:
    """Today on the same naive-UTC clock, for day-granularity comparisons."""
    return utcnow().date()


def end_of_day(day: date) -> datetime:
    """The last instant of a civil date, as a naive-UTC datetime.

    A job deadline is a *date* ("applications close on the 30th"), not an
    instant, so it is stored at the end of that day rather than the start: the
    role then keeps accepting applications for the whole day it names. Storing
    it this way also keeps expiry a single ``deadline < utcnow()`` comparison
    with no date truncation at the read sites, and because the value is
    end-of-day-UTC on both the write and the compare side, no local-time
    conversion ever happens and a deadline cannot drift across a timezone.
    """
    return datetime.combine(day, END_OF_DAY)