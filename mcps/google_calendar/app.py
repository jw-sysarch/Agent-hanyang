import os
import uuid
from typing import Any, Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from fastmcp import FastMCP
from dotenv import load_dotenv
from starlette.requests import Request
from starlette.responses import JSONResponse

# google-auth: OAuth refresh_token → Access Token
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest

# ─── 설정 ────────────────────────────────────────────────
load_dotenv()

CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"
SCOPES = ["https://www.googleapis.com/auth/calendar"]

VALID_SEND_UPDATES = {"all", "externalOnly", "none"}
VALID_RSVP = {"accepted", "declined", "tentative", "needsAction"}


def _get_env(key: str, default: str | None = None) -> str:
    value = os.getenv(key, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


# ─── 인증 (OAuth refresh_token) ─────────────────────────
_credentials: Credentials | None = None


def _get_credentials() -> Credentials:
    """OAuth refresh_token으로 Credentials 객체를 생성하고, 만료 시 자동 갱신."""
    global _credentials
    if _credentials is None:
        _credentials = Credentials(
            token=None,
            refresh_token=_get_env("GOOGLE_REFRESH_TOKEN"),
            client_id=_get_env("GOOGLE_CLIENT_ID"),
            client_secret=_get_env("GOOGLE_CLIENT_SECRET"),
            token_uri="https://oauth2.googleapis.com/token",
            scopes=SCOPES,
        )
    if not _credentials.valid:
        _credentials.refresh(GoogleAuthRequest())
    return _credentials


def _auth_headers() -> dict[str, str]:
    creds = _get_credentials()
    return {"Authorization": f"Bearer {creds.token}"}


def _calendar_id() -> str:
    return _get_env("GOOGLE_CALENDAR_ID", "primary")


def _validate_send_updates(value: str) -> str:
    if value not in VALID_SEND_UPDATES:
        raise ValueError(
            f"send_updates must be one of {sorted(VALID_SEND_UPDATES)}, got '{value}'"
        )
    return value


def _normalize_attendees(attendees: Optional[list]) -> list[dict[str, Any]]:
    """email 문자열 리스트 또는 dict 리스트를 Calendar API attendee 객체로 변환."""
    if not attendees:
        return []
    result: list[dict[str, Any]] = []
    for item in attendees:
        if isinstance(item, str):
            if item.strip():
                result.append({"email": item.strip()})
        elif isinstance(item, dict) and item.get("email"):
            result.append(item)
    return result


def _normalize_recurrence(recurrence: str | list[str] | None) -> Optional[list[str]]:
    """RRULE 문자열(들)을 Calendar API recurrence 리스트로 정규화."""
    if recurrence is None:
        return None
    items = [recurrence] if isinstance(recurrence, str) else list(recurrence)
    normalized: list[str] = []
    for item in items:
        if not item:
            continue
        s = item.strip()
        if s.startswith(("RRULE:", "EXDATE:", "RDATE:", "EXRULE:")):
            normalized.append(s)
        else:
            normalized.append(f"RRULE:{s}")
    return normalized


def _parse_rfc3339(value: str) -> datetime:
    """RFC3339 문자열을 timezone-aware datetime으로 파싱."""
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


# ─── FastMCP 서버 ────────────────────────────────────────
mcp = FastMCP("google-calendar")


@mcp.custom_route("/healthz", methods=["GET"], include_in_schema=False)
async def health_check(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "server": "google-calendar"})


# ─── MCP 도구: list_calendars ────────────────────────────
@mcp.tool
async def list_calendars() -> dict[str, Any]:
    """
    List all calendars accessible by this account.

    Returns a list of calendar summaries with their IDs.
    """
    url = f"{CALENDAR_API_BASE}/users/me/calendarList"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=_auth_headers())
        resp.raise_for_status()
        data = resp.json()

    calendars = [
        {
            "id": cal.get("id"),
            "summary": cal.get("summary"),
            "description": cal.get("description", ""),
            "access_role": cal.get("accessRole"),
            "primary": cal.get("primary", False),
        }
        for cal in data.get("items", [])
    ]
    return {"calendars": calendars, "count": len(calendars)}


# ─── MCP 도구: list_events ───────────────────────────────
@mcp.tool
async def list_events(
    calendar_id: Optional[str] = None,
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    max_results: int = 10,
    query: Optional[str] = None,
    page_token: Optional[str] = None,
    include_past: bool = False,
) -> dict[str, Any]:
    """
    List events from a Google Calendar with pagination support.

    Args:
        calendar_id: Calendar ID (defaults to env GOOGLE_CALENDAR_ID or 'primary').
        time_min: Lower bound (inclusive) for event start, RFC3339 e.g. '2026-05-20T00:00:00+09:00'.
                  When omitted, defaults to the current UTC time, so only upcoming events
                  are returned. To include past events without specifying a time, set
                  `include_past=True`.
        time_max: Upper bound (exclusive) for event start, RFC3339.
        max_results: Maximum number of events to return (default 10, max 2500).
        query: Free-text search terms to find events.
        page_token: Pass `next_page_token` from a prior response to get the next page.
        include_past: When True and time_min is not given, omit the default `now` floor
                      and return events regardless of how far in the past they started.
    """
    cal_id = calendar_id or _calendar_id()
    url = f"{CALENDAR_API_BASE}/calendars/{cal_id}/events"

    if time_min:
        effective_time_min = time_min
    elif include_past:
        effective_time_min = None
    else:
        effective_time_min = datetime.now(tz=ZoneInfo("UTC")).isoformat()

    params: dict[str, Any] = {
        "maxResults": min(max_results, 2500),
        "singleEvents": "true",
        "orderBy": "startTime",
    }
    if effective_time_min:
        params["timeMin"] = effective_time_min
    if time_max:
        params["timeMax"] = time_max
    if query:
        params["q"] = query
    if page_token:
        params["pageToken"] = page_token

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=_auth_headers(), params=params)
        resp.raise_for_status()
        data = resp.json()

    events = []
    for ev in data.get("items", []):
        events.append({
            "id": ev.get("id"),
            "summary": ev.get("summary"),
            "description": ev.get("description", ""),
            "location": ev.get("location", ""),
            "start": ev.get("start"),
            "end": ev.get("end"),
            "status": ev.get("status"),
            "html_link": ev.get("htmlLink"),
            "hangout_link": ev.get("hangoutLink"),
            "attendees": ev.get("attendees", []),
            "recurring_event_id": ev.get("recurringEventId"),
        })

    return {
        "events": events,
        "count": len(events),
        "next_page_token": data.get("nextPageToken"),
        "time_min_used": effective_time_min,
    }


# ─── MCP 도구: get_event ─────────────────────────────────
@mcp.tool
async def get_event(
    event_id: str,
    calendar_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Get details of a specific event.

    Args:
        event_id: The event ID to retrieve.
        calendar_id: Calendar ID (defaults to env GOOGLE_CALENDAR_ID or 'primary').
    """
    cal_id = calendar_id or _calendar_id()
    url = f"{CALENDAR_API_BASE}/calendars/{cal_id}/events/{event_id}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=_auth_headers())
        resp.raise_for_status()
        ev = resp.json()

    return {
        "id": ev.get("id"),
        "summary": ev.get("summary"),
        "description": ev.get("description", ""),
        "location": ev.get("location", ""),
        "start": ev.get("start"),
        "end": ev.get("end"),
        "status": ev.get("status"),
        "attendees": ev.get("attendees", []),
        "html_link": ev.get("htmlLink"),
        "hangout_link": ev.get("hangoutLink"),
        "conference_data": ev.get("conferenceData"),
        "recurrence": ev.get("recurrence", []),
        "recurring_event_id": ev.get("recurringEventId"),
        "created": ev.get("created"),
        "updated": ev.get("updated"),
    }


# ─── MCP 도구: create_event ──────────────────────────────
@mcp.tool
async def create_event(
    summary: str,
    start_datetime: str,
    end_datetime: str,
    calendar_id: Optional[str] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    timezone: str = "Asia/Seoul",
    attendees: Optional[list[str]] = None,
    with_meet: bool = False,
    recurrence: str | list[str] | None = None,
    send_updates: str = "none",
) -> dict[str, Any]:
    """
    Create a new event on Google Calendar.

    Args:
        summary: Title of the event.
        start_datetime: Start time in RFC3339, e.g. '2026-05-20T15:00:00'.
        end_datetime: End time in RFC3339.
        calendar_id: Calendar ID (defaults to env GOOGLE_CALENDAR_ID or 'primary').
        description: Optional description / notes for the event.
        location: Optional location string.
        timezone: IANA timezone, default 'Asia/Seoul'.
        attendees: Optional list of attendee email addresses.
        with_meet: When True, attaches an auto-generated Google Meet link.
        recurrence: Single RRULE string ('FREQ=WEEKLY;BYDAY=MO') or list of recurrence rules.
        send_updates: 'all' | 'externalOnly' | 'none'. Default 'none'. Use 'all' to send invitation emails.
    """
    _validate_send_updates(send_updates)
    cal_id = calendar_id or _calendar_id()
    url = f"{CALENDAR_API_BASE}/calendars/{cal_id}/events"

    body: dict[str, Any] = {
        "summary": summary,
        "start": {"dateTime": start_datetime, "timeZone": timezone},
        "end": {"dateTime": end_datetime, "timeZone": timezone},
    }
    if description:
        body["description"] = description
    if location:
        body["location"] = location

    normalized_attendees = _normalize_attendees(attendees)
    if normalized_attendees:
        body["attendees"] = normalized_attendees

    normalized_recurrence = _normalize_recurrence(recurrence)
    if normalized_recurrence:
        body["recurrence"] = normalized_recurrence

    params: dict[str, Any] = {"sendUpdates": send_updates}
    if with_meet:
        body["conferenceData"] = {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }
        params["conferenceDataVersion"] = 1

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=_auth_headers(), json=body, params=params)
        resp.raise_for_status()
        ev = resp.json()

    return {
        "id": ev.get("id"),
        "summary": ev.get("summary"),
        "start": ev.get("start"),
        "end": ev.get("end"),
        "html_link": ev.get("htmlLink"),
        "hangout_link": ev.get("hangoutLink"),
        "conference_data": ev.get("conferenceData"),
        "attendees": ev.get("attendees", []),
        "recurrence": ev.get("recurrence", []),
        "status": ev.get("status"),
    }


# ─── MCP 도구: quick_add_event ───────────────────────────
@mcp.tool
async def quick_add_event(
    text: str,
    calendar_id: Optional[str] = None,
    send_updates: str = "none",
) -> dict[str, Any]:
    """
    Create an event from a natural language string. Google parses date/time/title.

    Args:
        text: Natural language event, e.g. 'Lunch with Alice tomorrow 3pm'.
        calendar_id: Calendar ID (defaults to env or 'primary').
        send_updates: 'all' | 'externalOnly' | 'none'.
    """
    _validate_send_updates(send_updates)
    cal_id = calendar_id or _calendar_id()
    url = f"{CALENDAR_API_BASE}/calendars/{cal_id}/events/quickAdd"

    params = {"text": text, "sendUpdates": send_updates}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=_auth_headers(), params=params)
        resp.raise_for_status()
        ev = resp.json()

    return {
        "id": ev.get("id"),
        "summary": ev.get("summary"),
        "start": ev.get("start"),
        "end": ev.get("end"),
        "html_link": ev.get("htmlLink"),
        "status": ev.get("status"),
    }


# ─── MCP 도구: update_event ──────────────────────────────
@mcp.tool
async def update_event(
    event_id: str,
    calendar_id: Optional[str] = None,
    summary: Optional[str] = None,
    start_datetime: Optional[str] = None,
    end_datetime: Optional[str] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    timezone: str = "Asia/Seoul",
    recurrence: str | list[str] | None = None,
    send_updates: str = "none",
) -> dict[str, Any]:
    """
    Update an existing event with PATCH (only changed fields are sent).

    Args:
        event_id: The event ID to update.
        calendar_id: Calendar ID (defaults to env or 'primary').
        summary: New title for the event.
        start_datetime: New start time in RFC3339.
        end_datetime: New end time in RFC3339.
        description: New description.
        location: New location.
        timezone: IANA timezone for start/end, default 'Asia/Seoul'.
        recurrence: New RRULE (string or list). Pass empty list to clear recurrence.
        send_updates: 'all' | 'externalOnly' | 'none'.
    """
    _validate_send_updates(send_updates)
    cal_id = calendar_id or _calendar_id()
    url = f"{CALENDAR_API_BASE}/calendars/{cal_id}/events/{event_id}"

    patch: dict[str, Any] = {}
    if summary is not None:
        patch["summary"] = summary
    if description is not None:
        patch["description"] = description
    if location is not None:
        patch["location"] = location
    if start_datetime is not None:
        patch["start"] = {"dateTime": start_datetime, "timeZone": timezone}
    if end_datetime is not None:
        patch["end"] = {"dateTime": end_datetime, "timeZone": timezone}
    if recurrence is not None:
        patch["recurrence"] = _normalize_recurrence(recurrence) or []

    if not patch:
        return {"updated": False, "message": "No fields to update."}

    params = {"sendUpdates": send_updates}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.patch(url, headers=_auth_headers(), json=patch, params=params)
        resp.raise_for_status()
        ev = resp.json()

    return {
        "id": ev.get("id"),
        "summary": ev.get("summary"),
        "start": ev.get("start"),
        "end": ev.get("end"),
        "html_link": ev.get("htmlLink"),
        "status": ev.get("status"),
        "updated": ev.get("updated"),
    }


# ─── MCP 도구: delete_event ──────────────────────────────
@mcp.tool
async def delete_event(
    event_id: str,
    calendar_id: Optional[str] = None,
    send_updates: str = "none",
) -> dict[str, Any]:
    """
    Delete an event from Google Calendar.

    Args:
        event_id: The event ID to delete.
        calendar_id: Calendar ID (defaults to env or 'primary').
        send_updates: 'all' | 'externalOnly' | 'none'. Notifies attendees when 'all'.
    """
    _validate_send_updates(send_updates)
    cal_id = calendar_id or _calendar_id()
    url = f"{CALENDAR_API_BASE}/calendars/{cal_id}/events/{event_id}"

    params = {"sendUpdates": send_updates}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.delete(url, headers=_auth_headers(), params=params)
        resp.raise_for_status()

    return {
        "deleted": True,
        "event_id": event_id,
        "calendar_id": cal_id,
    }


# ─── MCP 도구: add_attendees ─────────────────────────────
@mcp.tool
async def add_attendees(
    event_id: str,
    attendees: list[str],
    calendar_id: Optional[str] = None,
    send_updates: str = "all",
) -> dict[str, Any]:
    """
    Add attendees to an existing event (merges with current attendee list).

    Args:
        event_id: Event ID to modify.
        attendees: List of email addresses to add.
        calendar_id: Calendar ID (defaults to env or 'primary').
        send_updates: 'all' (default) | 'externalOnly' | 'none'.
    """
    _validate_send_updates(send_updates)
    cal_id = calendar_id or _calendar_id()
    url = f"{CALENDAR_API_BASE}/calendars/{cal_id}/events/{event_id}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        get_resp = await client.get(url, headers=_auth_headers())
        get_resp.raise_for_status()
        existing = get_resp.json()

    current = list(existing.get("attendees") or [])
    existing_emails = {(a.get("email") or "").lower() for a in current}
    for email in attendees:
        if not email:
            continue
        if email.lower() not in existing_emails:
            current.append({"email": email})
            existing_emails.add(email.lower())

    params = {"sendUpdates": send_updates}
    patch = {"attendees": current}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.patch(url, headers=_auth_headers(), json=patch, params=params)
        resp.raise_for_status()
        ev = resp.json()

    return {
        "id": ev.get("id"),
        "summary": ev.get("summary"),
        "attendees": ev.get("attendees", []),
        "html_link": ev.get("htmlLink"),
    }


# ─── MCP 도구: remove_attendees ──────────────────────────
@mcp.tool
async def remove_attendees(
    event_id: str,
    attendees: list[str],
    calendar_id: Optional[str] = None,
    send_updates: str = "all",
) -> dict[str, Any]:
    """
    Remove attendees from an event.

    Args:
        event_id: Event ID.
        attendees: List of email addresses to remove.
        calendar_id: Calendar ID (defaults to env or 'primary').
        send_updates: 'all' | 'externalOnly' | 'none'.
    """
    _validate_send_updates(send_updates)
    cal_id = calendar_id or _calendar_id()
    url = f"{CALENDAR_API_BASE}/calendars/{cal_id}/events/{event_id}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        get_resp = await client.get(url, headers=_auth_headers())
        get_resp.raise_for_status()
        existing = get_resp.json()

    remove_set = {(e or "").lower() for e in attendees if e}
    current = existing.get("attendees") or []
    filtered = [a for a in current if (a.get("email") or "").lower() not in remove_set]

    params = {"sendUpdates": send_updates}
    patch = {"attendees": filtered}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.patch(url, headers=_auth_headers(), json=patch, params=params)
        resp.raise_for_status()
        ev = resp.json()

    return {
        "id": ev.get("id"),
        "summary": ev.get("summary"),
        "attendees": ev.get("attendees", []),
        "html_link": ev.get("htmlLink"),
    }


# ─── MCP 도구: respond_to_event ──────────────────────────
@mcp.tool
async def respond_to_event(
    event_id: str,
    response: str,
    user_email: Optional[str] = None,
    calendar_id: Optional[str] = None,
    send_updates: str = "all",
) -> dict[str, Any]:
    """
    Respond to an event invitation (RSVP).

    Args:
        event_id: Event ID.
        response: 'accepted' | 'declined' | 'tentative' | 'needsAction'.
        user_email: Attendee email to update. Defaults to env GOOGLE_USER_EMAIL.
        calendar_id: Calendar ID (defaults to env or 'primary').
        send_updates: 'all' | 'externalOnly' | 'none'.
    """
    if response not in VALID_RSVP:
        return {"error": f"response must be one of {sorted(VALID_RSVP)}"}
    _validate_send_updates(send_updates)

    email = user_email or os.getenv("GOOGLE_USER_EMAIL")
    if not email:
        return {"error": "user_email is required (or set GOOGLE_USER_EMAIL env var)."}

    cal_id = calendar_id or _calendar_id()
    url = f"{CALENDAR_API_BASE}/calendars/{cal_id}/events/{event_id}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        get_resp = await client.get(url, headers=_auth_headers())
        get_resp.raise_for_status()
        existing = get_resp.json()

    attendees = list(existing.get("attendees") or [])
    found = False
    for a in attendees:
        if (a.get("email") or "").lower() == email.lower():
            a["responseStatus"] = response
            found = True
            break
    if not found:
        attendees.append({"email": email, "responseStatus": response, "self": True})

    params = {"sendUpdates": send_updates}
    patch = {"attendees": attendees}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.patch(url, headers=_auth_headers(), json=patch, params=params)
        resp.raise_for_status()
        ev = resp.json()

    return {
        "id": ev.get("id"),
        "summary": ev.get("summary"),
        "response_status": response,
        "user_email": email,
        "html_link": ev.get("htmlLink"),
    }


# ─── MCP 도구: move_event ────────────────────────────────
@mcp.tool
async def move_event(
    event_id: str,
    destination_calendar_id: str,
    source_calendar_id: Optional[str] = None,
    send_updates: str = "none",
) -> dict[str, Any]:
    """
    Move an event from one calendar to another.

    Args:
        event_id: Event ID.
        destination_calendar_id: Target calendar ID.
        source_calendar_id: Source calendar ID (defaults to env or 'primary').
        send_updates: 'all' | 'externalOnly' | 'none'.
    """
    _validate_send_updates(send_updates)
    src_id = source_calendar_id or _calendar_id()
    url = f"{CALENDAR_API_BASE}/calendars/{src_id}/events/{event_id}/move"

    params = {
        "destination": destination_calendar_id,
        "sendUpdates": send_updates,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=_auth_headers(), params=params)
        resp.raise_for_status()
        ev = resp.json()

    return {
        "id": ev.get("id"),
        "summary": ev.get("summary"),
        "html_link": ev.get("htmlLink"),
        "source_calendar_id": src_id,
        "destination_calendar_id": destination_calendar_id,
    }


# ─── MCP 도구: find_free_slots ───────────────────────────
@mcp.tool
async def find_free_slots(
    time_min: str,
    time_max: str,
    calendar_ids: Optional[list[str]] = None,
    slot_duration_minutes: int = 30,
    timezone: str = "Asia/Seoul",
    working_hours_start: Optional[str] = None,
    working_hours_end: Optional[str] = None,
) -> dict[str, Any]:
    """
    Find free time slots common to multiple calendars within a range.

    Uses Google Calendar FreeBusy API to fetch busy intervals, then computes
    the complement within [time_min, time_max] and (optionally) within working hours.

    Args:
        time_min: Range start in RFC3339, e.g. '2026-05-20T09:00:00+09:00'.
        time_max: Range end in RFC3339.
        calendar_ids: List of calendar IDs to check. Defaults to [primary].
        slot_duration_minutes: Minimum slot length to return. Default 30.
        timezone: IANA timezone for working hours interpretation. Default 'Asia/Seoul'.
        working_hours_start: Optional 'HH:MM', restricts slots to this start each day.
        working_hours_end: Optional 'HH:MM', restricts slots to this end each day.
    """
    cal_ids = calendar_ids or [_calendar_id()]
    url = f"{CALENDAR_API_BASE}/freeBusy"

    body = {
        "timeMin": time_min,
        "timeMax": time_max,
        "timeZone": timezone,
        "items": [{"id": cid} for cid in cal_ids],
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=_auth_headers(), json=body)
        resp.raise_for_status()
        data = resp.json()

    calendars_field = data.get("calendars", {})
    busy_intervals: list[tuple[datetime, datetime]] = []
    errors: dict[str, Any] = {}
    for cid, info in calendars_field.items():
        if info.get("errors"):
            errors[cid] = info["errors"]
        for b in info.get("busy", []):
            try:
                start = _parse_rfc3339(b["start"])
                end = _parse_rfc3339(b["end"])
                busy_intervals.append((start, end))
            except (KeyError, ValueError):
                continue

    busy_intervals.sort()
    merged: list[tuple[datetime, datetime]] = []
    for start, end in busy_intervals:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    range_start = _parse_rfc3339(time_min)
    range_end = _parse_rfc3339(time_max)

    free_intervals: list[tuple[datetime, datetime]] = []
    cursor = range_start
    for bstart, bend in merged:
        if bstart > cursor:
            free_intervals.append((cursor, min(bstart, range_end)))
        cursor = max(cursor, bend)
        if cursor >= range_end:
            break
    if cursor < range_end:
        free_intervals.append((cursor, range_end))

    if working_hours_start and working_hours_end:
        try:
            wh_start_h, wh_start_m = (int(x) for x in working_hours_start.split(":"))
            wh_end_h, wh_end_m = (int(x) for x in working_hours_end.split(":"))
            tz = ZoneInfo(timezone)
        except (ValueError, AttributeError):
            return {"error": "working_hours_start/end must be 'HH:MM' format."}
        except ZoneInfoNotFoundError:
            return {"error": f"Unknown timezone: {timezone}"}

        filtered: list[tuple[datetime, datetime]] = []
        for f_start, f_end in free_intervals:
            local_start = f_start.astimezone(tz)
            local_end = f_end.astimezone(tz)
            day = local_start.date()
            while day <= local_end.date():
                day_wh_start = datetime(
                    day.year, day.month, day.day,
                    wh_start_h, wh_start_m, tzinfo=tz,
                )
                day_wh_end = datetime(
                    day.year, day.month, day.day,
                    wh_end_h, wh_end_m, tzinfo=tz,
                )
                slot_start = max(local_start, day_wh_start)
                slot_end = min(local_end, day_wh_end)
                if slot_start < slot_end:
                    filtered.append((slot_start, slot_end))
                day = day + timedelta(days=1)
        free_intervals = filtered

    min_duration = timedelta(minutes=slot_duration_minutes)
    slots = []
    for s, e in free_intervals:
        if e - s >= min_duration:
            slots.append({
                "start": s.isoformat(),
                "end": e.isoformat(),
                "duration_minutes": int((e - s).total_seconds() // 60),
            })

    result: dict[str, Any] = {
        "slots": slots,
        "count": len(slots),
        "calendars_checked": cal_ids,
        "slot_duration_minutes": slot_duration_minutes,
    }
    if errors:
        result["calendar_errors"] = errors
    return result


# ─── 서버 실행 ───────────────────────────────────────────
if __name__ == "__main__":
    transport = os.getenv("FASTMCP_TRANSPORT", "streamable-http")
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8002"))
    mcp.run(transport=transport, host=host, port=port)
