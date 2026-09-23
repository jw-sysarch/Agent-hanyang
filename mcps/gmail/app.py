import asyncio
import base64
import os
from email.message import EmailMessage
from typing import Any, Optional

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

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


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


# ─── 헬퍼: 헤더/본문 파싱 ────────────────────────────────
def _extract_headers(payload: dict[str, Any], keys: list[str]) -> dict[str, str]:
    """payload.headers 에서 원하는 키만 골라 dict로 반환 (대소문자 무시)."""
    wanted = {k.lower(): k for k in keys}
    result: dict[str, str] = {}
    for h in payload.get("headers", []) or []:
        name = (h.get("name") or "").lower()
        if name in wanted:
            result[wanted[name]] = h.get("value", "")
    return result


def _decode_b64url(data: str) -> str:
    """Gmail body.data 는 base64url(padding 없음). 안전하게 디코드."""
    if not data:
        return ""
    padded = data + "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        return ""


def _extract_body(payload: dict[str, Any]) -> dict[str, str]:
    """payload 재귀 탐색하여 text/plain 우선, 없으면 text/html 본문 반환."""
    plain: list[str] = []
    html: list[str] = []

    def walk(part: dict[str, Any]) -> None:
        mime_type = part.get("mimeType", "")
        body = part.get("body") or {}
        data = body.get("data")
        if data:
            decoded = _decode_b64url(data)
            if mime_type == "text/plain":
                plain.append(decoded)
            elif mime_type == "text/html":
                html.append(decoded)
        for sub in part.get("parts", []) or []:
            walk(sub)

    walk(payload)
    return {
        "text": "\n".join(plain).strip(),
        "html": "\n".join(html).strip(),
    }


def _extract_attachments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """첨부파일 메타데이터만 (실제 데이터는 별도 endpoint로 받아야 함)."""
    attachments: list[dict[str, Any]] = []

    def walk(part: dict[str, Any]) -> None:
        filename = part.get("filename") or ""
        body = part.get("body") or {}
        if filename and body.get("attachmentId"):
            attachments.append({
                "filename": filename,
                "mime_type": part.get("mimeType", ""),
                "size": body.get("size", 0),
                "attachment_id": body.get("attachmentId"),
            })
        for sub in part.get("parts", []) or []:
            walk(sub)

    walk(payload)
    return attachments


def _normalize_addr_list(value: list[str] | str | None) -> Optional[str]:
    """email 주소 list 또는 단일 문자열을 RFC 2822용 콤마 결합 문자열로."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    cleaned = [v.strip() for v in value if v and v.strip()]
    return ", ".join(cleaned) if cleaned else None


def _build_raw_message(
    to: list[str] | str,
    subject: str,
    body: str,
    cc: list[str] | str | None = None,
    bcc: list[str] | str | None = None,
    from_addr: Optional[str] = None,
    in_reply_to: Optional[str] = None,
    references: Optional[str] = None,
    html: bool = False,
) -> str:
    """EmailMessage → base64url 인코딩된 RFC 2822 raw 문자열."""
    msg = EmailMessage()
    to_str = _normalize_addr_list(to)
    if not to_str:
        raise ValueError("`to` is required and cannot be empty.")
    msg["To"] = to_str
    msg["Subject"] = subject or ""

    cc_str = _normalize_addr_list(cc)
    if cc_str:
        msg["Cc"] = cc_str
    bcc_str = _normalize_addr_list(bcc)
    if bcc_str:
        msg["Bcc"] = bcc_str
    if from_addr:
        msg["From"] = from_addr
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references

    if html:
        msg.set_content("HTML email — view in an HTML-capable client.")
        msg.add_alternative(body, subtype="html")
    else:
        msg.set_content(body or "")

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    return raw.rstrip("=")


async def _fetch_reply_context(
    client: httpx.AsyncClient,
    message_id: str,
) -> dict[str, str]:
    """원본 메시지의 Message-ID / References / Subject / threadId를 가져와 답장 헤더 구성."""
    resp = await client.get(
        f"{GMAIL_API_BASE}/users/me/messages/{message_id}",
        headers=_auth_headers(),
        params={
            "format": "metadata",
            "metadataHeaders": ["Message-ID", "References", "Subject"],
        },
    )
    resp.raise_for_status()
    src = resp.json()
    hdrs = _extract_headers(src.get("payload") or {}, ["Message-ID", "References", "Subject"])
    src_msg_id = hdrs.get("Message-ID", "")
    src_refs = hdrs.get("References", "")
    new_refs = (src_refs + " " + src_msg_id).strip() if src_refs else src_msg_id
    src_subject = hdrs.get("Subject", "")
    new_subject = src_subject if src_subject.lower().startswith("re:") else f"Re: {src_subject}"
    return {
        "thread_id": src.get("threadId", ""),
        "in_reply_to": src_msg_id,
        "references": new_refs,
        "subject": new_subject,
    }


# ─── FastMCP 서버 ────────────────────────────────────────
mcp = FastMCP("gmail")


@mcp.custom_route("/healthz", methods=["GET"], include_in_schema=False)
async def health_check(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "server": "gmail"})


# ─── MCP 도구: get_profile ───────────────────────────────
@mcp.tool
async def get_profile() -> dict[str, Any]:
    """
    Get the authenticated user's Gmail profile.

    Returns email address and total message/thread counts.
    """
    url = f"{GMAIL_API_BASE}/users/me/profile"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=_auth_headers())
        resp.raise_for_status()
        data = resp.json()

    return {
        "email_address": data.get("emailAddress"),
        "messages_total": data.get("messagesTotal"),
        "threads_total": data.get("threadsTotal"),
        "history_id": data.get("historyId"),
    }


# ─── MCP 도구: list_labels ───────────────────────────────
@mcp.tool
async def list_labels() -> dict[str, Any]:
    """
    List all Gmail labels (system + user-defined).

    Use this first to resolve label names → IDs before calling modify_labels.
    """
    url = f"{GMAIL_API_BASE}/users/me/labels"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=_auth_headers())
        resp.raise_for_status()
        data = resp.json()

    labels = [
        {
            "id": lbl.get("id"),
            "name": lbl.get("name"),
            "type": lbl.get("type"),
            "message_list_visibility": lbl.get("messageListVisibility"),
            "label_list_visibility": lbl.get("labelListVisibility"),
        }
        for lbl in data.get("labels", []) or []
    ]
    return {"labels": labels, "count": len(labels)}


# ─── MCP 도구: list_messages ─────────────────────────────
@mcp.tool
async def list_messages(
    query: Optional[str] = None,
    max_results: int = 10,
    label_ids: Optional[list[str]] = None,
    page_token: Optional[str] = None,
    include_spam_trash: bool = False,
    fetch_metadata: bool = True,
) -> dict[str, Any]:
    """
    Search/list Gmail messages.

    Args:
        query: Gmail search operator string, e.g. 'from:foo@bar.com is:unread newer_than:7d
                has:attachment subject:invoice'.
        max_results: Number of messages to return (default 10, max 100).
        label_ids: Filter by label IDs (use list_labels to resolve names → IDs).
        page_token: Pass `next_page_token` from a prior response for pagination.
        include_spam_trash: When True, include messages in SPAM and TRASH.
        fetch_metadata: When True (default), fetches Subject/From/To/Date/snippet for
                        each result in parallel. Set False to skip and return only ids.
    """
    url = f"{GMAIL_API_BASE}/users/me/messages"
    params: dict[str, Any] = {
        "maxResults": min(max_results, 100),
        "includeSpamTrash": "true" if include_spam_trash else "false",
    }
    if query:
        params["q"] = query
    if label_ids:
        params["labelIds"] = label_ids
    if page_token:
        params["pageToken"] = page_token

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=_auth_headers(), params=params)
        resp.raise_for_status()
        data = resp.json()

        message_stubs = data.get("messages", []) or []

        if not fetch_metadata or not message_stubs:
            messages = [
                {"id": m.get("id"), "thread_id": m.get("threadId")}
                for m in message_stubs
            ]
            return {
                "messages": messages,
                "count": len(messages),
                "next_page_token": data.get("nextPageToken"),
                "result_size_estimate": data.get("resultSizeEstimate"),
            }

        headers = _auth_headers()
        meta_params = {
            "format": "metadata",
            "metadataHeaders": ["Subject", "From", "To", "Cc", "Date"],
        }

        async def fetch_meta(msg_id: str) -> dict[str, Any]:
            r = await client.get(
                f"{GMAIL_API_BASE}/users/me/messages/{msg_id}",
                headers=headers,
                params=meta_params,
            )
            r.raise_for_status()
            return r.json()

        details = await asyncio.gather(
            *(fetch_meta(m["id"]) for m in message_stubs if m.get("id"))
        )

    messages = []
    for ev in details:
        payload = ev.get("payload") or {}
        hdrs = _extract_headers(payload, ["Subject", "From", "To", "Cc", "Date"])
        messages.append({
            "id": ev.get("id"),
            "thread_id": ev.get("threadId"),
            "label_ids": ev.get("labelIds", []),
            "snippet": ev.get("snippet", ""),
            "subject": hdrs.get("Subject", ""),
            "from": hdrs.get("From", ""),
            "to": hdrs.get("To", ""),
            "cc": hdrs.get("Cc", ""),
            "date": hdrs.get("Date", ""),
            "internal_date": ev.get("internalDate"),
        })

    return {
        "messages": messages,
        "count": len(messages),
        "next_page_token": data.get("nextPageToken"),
        "result_size_estimate": data.get("resultSizeEstimate"),
    }


# ─── MCP 도구: get_message ───────────────────────────────
@mcp.tool
async def get_message(
    message_id: str,
    format: str = "full",
    include_body: bool = True,
) -> dict[str, Any]:
    """
    Get a single Gmail message with headers, body, and attachment metadata.

    Args:
        message_id: The Gmail message ID.
        format: 'full' (default, with body) | 'metadata' (headers only) | 'minimal' | 'raw'.
        include_body: When True (default) and format='full', decodes text/plain and text/html
                      body parts. Set False to skip body decoding for speed.
    """
    if format not in {"full", "metadata", "minimal", "raw"}:
        return {"error": "format must be one of 'full' | 'metadata' | 'minimal' | 'raw'."}

    url = f"{GMAIL_API_BASE}/users/me/messages/{message_id}"
    params: dict[str, Any] = {"format": format}
    if format == "metadata":
        params["metadataHeaders"] = ["Subject", "From", "To", "Cc", "Bcc", "Date",
                                     "Message-ID", "In-Reply-To", "References"]

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=_auth_headers(), params=params)
        resp.raise_for_status()
        msg = resp.json()

    payload = msg.get("payload") or {}
    hdrs = _extract_headers(
        payload,
        ["Subject", "From", "To", "Cc", "Bcc", "Date",
         "Message-ID", "In-Reply-To", "References"],
    )

    result: dict[str, Any] = {
        "id": msg.get("id"),
        "thread_id": msg.get("threadId"),
        "label_ids": msg.get("labelIds", []),
        "snippet": msg.get("snippet", ""),
        "internal_date": msg.get("internalDate"),
        "size_estimate": msg.get("sizeEstimate"),
        "subject": hdrs.get("Subject", ""),
        "from": hdrs.get("From", ""),
        "to": hdrs.get("To", ""),
        "cc": hdrs.get("Cc", ""),
        "bcc": hdrs.get("Bcc", ""),
        "date": hdrs.get("Date", ""),
        "message_id_header": hdrs.get("Message-ID", ""),
        "in_reply_to": hdrs.get("In-Reply-To", ""),
        "references": hdrs.get("References", ""),
    }

    if format == "full" and include_body:
        body = _extract_body(payload)
        result["body_text"] = body["text"]
        result["body_html"] = body["html"]
        result["attachments"] = _extract_attachments(payload)

    if format == "raw":
        result["raw"] = msg.get("raw", "")

    return result


# ─── MCP 도구: get_thread ────────────────────────────────
@mcp.tool
async def get_thread(
    thread_id: str,
    include_body: bool = True,
) -> dict[str, Any]:
    """
    Get all messages in a Gmail thread (conversation).

    Args:
        thread_id: The Gmail thread ID (also seen as `threadId` on messages).
        include_body: When True (default), decodes text/plain/html for each message.
    """
    url = f"{GMAIL_API_BASE}/users/me/threads/{thread_id}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=_auth_headers(), params={"format": "full"})
        resp.raise_for_status()
        data = resp.json()

    messages: list[dict[str, Any]] = []
    for msg in data.get("messages", []) or []:
        payload = msg.get("payload") or {}
        hdrs = _extract_headers(
            payload,
            ["Subject", "From", "To", "Cc", "Date", "Message-ID", "In-Reply-To"],
        )
        entry: dict[str, Any] = {
            "id": msg.get("id"),
            "label_ids": msg.get("labelIds", []),
            "snippet": msg.get("snippet", ""),
            "internal_date": msg.get("internalDate"),
            "subject": hdrs.get("Subject", ""),
            "from": hdrs.get("From", ""),
            "to": hdrs.get("To", ""),
            "cc": hdrs.get("Cc", ""),
            "date": hdrs.get("Date", ""),
            "message_id_header": hdrs.get("Message-ID", ""),
            "in_reply_to": hdrs.get("In-Reply-To", ""),
        }
        if include_body:
            body = _extract_body(payload)
            entry["body_text"] = body["text"]
            entry["body_html"] = body["html"]
            entry["attachments"] = _extract_attachments(payload)
        messages.append(entry)

    return {
        "id": data.get("id"),
        "history_id": data.get("historyId"),
        "messages": messages,
        "count": len(messages),
    }


# ─── MCP 도구: send_message ──────────────────────────────
@mcp.tool
async def send_message(
    to: list[str] | str,
    subject: str,
    body: str,
    cc: list[str] | str | None = None,
    bcc: list[str] | str | None = None,
    html: bool = False,
    reply_to_message_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Send an email via Gmail. Supports plain text or HTML, and threaded replies.

    Args:
        to: Recipient email address or list of addresses.
        subject: Email subject. Ignored when `reply_to_message_id` is set
                 (subject is taken from the original message with 'Re: ' prefix).
        body: Body content. If `html=True`, this is rendered as HTML.
        cc: Optional Cc recipient(s).
        bcc: Optional Bcc recipient(s).
        html: When True, send `body` as text/html (with a plain-text fallback).
        reply_to_message_id: When set, fetches the original message's Message-ID,
                             References, Subject, and threadId, then sends a reply
                             that keeps the conversation threaded in Gmail.
    """
    url = f"{GMAIL_API_BASE}/users/me/messages/send"

    async with httpx.AsyncClient(timeout=30.0) as client:
        thread_id: Optional[str] = None
        in_reply_to: Optional[str] = None
        references: Optional[str] = None
        effective_subject = subject

        if reply_to_message_id:
            ctx = await _fetch_reply_context(client, reply_to_message_id)
            thread_id = ctx["thread_id"] or None
            in_reply_to = ctx["in_reply_to"] or None
            references = ctx["references"] or None
            effective_subject = ctx["subject"] or subject

        raw = _build_raw_message(
            to=to,
            subject=effective_subject,
            body=body,
            cc=cc,
            bcc=bcc,
            in_reply_to=in_reply_to,
            references=references,
            html=html,
        )

        payload: dict[str, Any] = {"raw": raw}
        if thread_id:
            payload["threadId"] = thread_id

        resp = await client.post(url, headers=_auth_headers(), json=payload)
        resp.raise_for_status()
        sent = resp.json()

    return {
        "id": sent.get("id"),
        "thread_id": sent.get("threadId"),
        "label_ids": sent.get("labelIds", []),
        "subject": effective_subject,
        "to": _normalize_addr_list(to),
        "cc": _normalize_addr_list(cc),
        "is_reply": bool(reply_to_message_id),
    }


# ─── MCP 도구: create_draft ──────────────────────────────
@mcp.tool
async def create_draft(
    to: list[str] | str,
    subject: str,
    body: str,
    cc: list[str] | str | None = None,
    bcc: list[str] | str | None = None,
    html: bool = False,
    reply_to_message_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Create a Gmail draft (does NOT send). Use `send_draft` to send it later.

    Same arguments as `send_message`. Returns a `draft_id` you can pass to
    `send_draft` or `delete_draft`.
    """
    url = f"{GMAIL_API_BASE}/users/me/drafts"

    async with httpx.AsyncClient(timeout=30.0) as client:
        thread_id: Optional[str] = None
        in_reply_to: Optional[str] = None
        references: Optional[str] = None
        effective_subject = subject

        if reply_to_message_id:
            ctx = await _fetch_reply_context(client, reply_to_message_id)
            thread_id = ctx["thread_id"] or None
            in_reply_to = ctx["in_reply_to"] or None
            references = ctx["references"] or None
            effective_subject = ctx["subject"] or subject

        raw = _build_raw_message(
            to=to,
            subject=effective_subject,
            body=body,
            cc=cc,
            bcc=bcc,
            in_reply_to=in_reply_to,
            references=references,
            html=html,
        )

        message: dict[str, Any] = {"raw": raw}
        if thread_id:
            message["threadId"] = thread_id

        resp = await client.post(
            url, headers=_auth_headers(), json={"message": message}
        )
        resp.raise_for_status()
        draft = resp.json()

    inner_msg = draft.get("message") or {}
    return {
        "draft_id": draft.get("id"),
        "message_id": inner_msg.get("id"),
        "thread_id": inner_msg.get("threadId"),
        "subject": effective_subject,
        "to": _normalize_addr_list(to),
        "is_reply": bool(reply_to_message_id),
    }


# ─── MCP 도구: send_draft ────────────────────────────────
@mcp.tool
async def send_draft(draft_id: str) -> dict[str, Any]:
    """
    Send an existing Gmail draft.

    Args:
        draft_id: The draft ID returned by `create_draft`.
    """
    url = f"{GMAIL_API_BASE}/users/me/drafts/send"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=_auth_headers(), json={"id": draft_id})
        resp.raise_for_status()
        sent = resp.json()

    return {
        "id": sent.get("id"),
        "thread_id": sent.get("threadId"),
        "label_ids": sent.get("labelIds", []),
        "draft_id": draft_id,
    }


# ─── MCP 도구: delete_draft ──────────────────────────────
@mcp.tool
async def delete_draft(draft_id: str) -> dict[str, Any]:
    """
    Delete a Gmail draft (does not affect sent messages).

    Args:
        draft_id: The draft ID to delete.
    """
    url = f"{GMAIL_API_BASE}/users/me/drafts/{draft_id}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.delete(url, headers=_auth_headers())
        resp.raise_for_status()

    return {"deleted": True, "draft_id": draft_id}


# ─── MCP 도구: modify_labels ─────────────────────────────
@mcp.tool
async def modify_labels(
    message_id: str,
    add_label_ids: Optional[list[str]] = None,
    remove_label_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Add or remove labels on a Gmail message. Common system labels:
    INBOX, UNREAD, STARRED, IMPORTANT, SPAM, TRASH, SENT, DRAFT.

    To mark a message as read: remove_label_ids=['UNREAD'].
    To star a message: add_label_ids=['STARRED'].
    To archive: remove_label_ids=['INBOX'].

    Args:
        message_id: The Gmail message ID.
        add_label_ids: Label IDs to add (use list_labels to resolve names → IDs).
        remove_label_ids: Label IDs to remove.
    """
    add = [l for l in (add_label_ids or []) if l]
    remove = [l for l in (remove_label_ids or []) if l]
    if not add and not remove:
        return {"updated": False, "message": "No labels to add or remove."}

    url = f"{GMAIL_API_BASE}/users/me/messages/{message_id}/modify"
    body: dict[str, Any] = {}
    if add:
        body["addLabelIds"] = add
    if remove:
        body["removeLabelIds"] = remove

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=_auth_headers(), json=body)
        resp.raise_for_status()
        msg = resp.json()

    return {
        "id": msg.get("id"),
        "thread_id": msg.get("threadId"),
        "label_ids": msg.get("labelIds", []),
        "added": add,
        "removed": remove,
    }


# ─── MCP 도구: trash_message ─────────────────────────────
@mcp.tool
async def trash_message(message_id: str) -> dict[str, Any]:
    """
    Move a Gmail message to TRASH (recoverable for 30 days, NOT permanent delete).

    Args:
        message_id: The Gmail message ID.
    """
    url = f"{GMAIL_API_BASE}/users/me/messages/{message_id}/trash"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=_auth_headers())
        resp.raise_for_status()
        msg = resp.json()

    return {
        "trashed": True,
        "id": msg.get("id"),
        "thread_id": msg.get("threadId"),
        "label_ids": msg.get("labelIds", []),
    }


# ─── MCP 도구: untrash_message ───────────────────────────
@mcp.tool
async def untrash_message(message_id: str) -> dict[str, Any]:
    """
    Restore a Gmail message from TRASH back to its previous labels.

    Args:
        message_id: The Gmail message ID currently in TRASH.
    """
    url = f"{GMAIL_API_BASE}/users/me/messages/{message_id}/untrash"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=_auth_headers())
        resp.raise_for_status()
        msg = resp.json()

    return {
        "untrashed": True,
        "id": msg.get("id"),
        "thread_id": msg.get("threadId"),
        "label_ids": msg.get("labelIds", []),
    }


# ─── 서버 실행 ───────────────────────────────────────────
if __name__ == "__main__":
    transport = os.getenv("FASTMCP_TRANSPORT", "streamable-http")
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8008"))
    mcp.run(transport=transport, host=host, port=port)
