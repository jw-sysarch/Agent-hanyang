import os
from typing import Any, Optional

from dotenv import load_dotenv
from fastmcp import FastMCP
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from starlette.requests import Request
from starlette.responses import JSONResponse

load_dotenv()

mcp = FastMCP("google-docs-drive-mcp")

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]


def get_credentials():
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")

    missing = [
        name
        for name, value in {
            "GOOGLE_CLIENT_ID": client_id,
            "GOOGLE_CLIENT_SECRET": client_secret,
            "GOOGLE_REFRESH_TOKEN": refresh_token,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(f"Missing Google OAuth env values: {', '.join(missing)}")

    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    credentials.refresh(GoogleAuthRequest())
    return credentials


def get_docs_service():
    credentials = get_credentials()
    return build("docs", "v1", credentials=credentials)


def get_drive_service():
    credentials = get_credentials()
    return build("drive", "v3", credentials=credentials)


def get_default_parent_folder_id() -> Optional[str]:
    return os.getenv("GOOGLE_DRIVE_DEFAULT_FOLDER_ID") or None


def extract_text_from_document(doc: dict[str, Any]) -> str:
    content = doc.get("body", {}).get("content", [])
    parts = []

    for element in content:
        paragraph = element.get("paragraph")
        if not paragraph:
            continue

        for para_element in paragraph.get("elements", []):
            text_run = para_element.get("textRun")
            if text_run and "content" in text_run:
                parts.append(text_run["content"])

    return "".join(parts)


@mcp.tool()
def create_document(title: str, parent_folder_id: Optional[str] = None) -> dict[str, Any]:
    docs_service = get_docs_service()
    drive_service = get_drive_service()
    target_parent_folder_id = parent_folder_id or get_default_parent_folder_id()

    try:
        if target_parent_folder_id:
            file_meta = drive_service.files().create(
                body={
                    "name": title,
                    "mimeType": "application/vnd.google-apps.document",
                    "parents": [target_parent_folder_id],
                },
                fields="id, name, mimeType, parents, webViewLink, createdTime, modifiedTime",
                supportsAllDrives=True,
            ).execute()

            doc = docs_service.documents().get(documentId=file_meta["id"]).execute()
            return {
                "document_id": file_meta.get("id"),
                "title": doc.get("title") or file_meta.get("name"),
                "revision_id": doc.get("revisionId"),
                "parent_folder_id": target_parent_folder_id,
                "drive": file_meta,
            }

        doc = docs_service.documents().create(body={"title": title}).execute()
        document_id = doc.get("documentId")
        file_meta = drive_service.files().get(
            fileId=document_id,
            fields="id, name, mimeType, parents, webViewLink, createdTime, modifiedTime",
            supportsAllDrives=True,
        ).execute()

        return {
            "document_id": document_id,
            "title": doc.get("title"),
            "revision_id": doc.get("revisionId"),
            "parent_folder_id": target_parent_folder_id,
            "drive": file_meta,
        }
    except HttpError as error:
        return {
            "error": "google_drive_permission_error",
            "message": (
                "Google Docs creation failed. Share a Drive folder with the "
                "service account email as editor, then set "
                "GOOGLE_DRIVE_DEFAULT_FOLDER_ID to that folder id or pass "
                "parent_folder_id."
            ),
            "details": str(error),
        }


@mcp.tool()
def get_document(document_id: str) -> dict[str, Any]:
    docs_service = get_docs_service()
    drive_service = get_drive_service()

    doc = docs_service.documents().get(documentId=document_id).execute()
    file_meta = drive_service.files().get(
        fileId=document_id,
        fields="id, name, mimeType, parents, webViewLink, createdTime, modifiedTime"
    ).execute()

    return {
        "document_id": doc.get("documentId"),
        "title": doc.get("title"),
        "revision_id": doc.get("revisionId"),
        "text": extract_text_from_document(doc),
        "drive": file_meta,
        "raw": doc,
    }


@mcp.tool()
def append_to_document(document_id: str, text: str) -> dict[str, Any]:
    docs_service = get_docs_service()
    doc = docs_service.documents().get(documentId=document_id).execute()

    end_index = doc.get("body", {}).get("content", [])[-1].get("endIndex", 1)
    insert_index = max(1, end_index - 1)

    requests = [
        {
            "insertText": {
                "location": {"index": insert_index},
                "text": text
            }
        }
    ]

    result = docs_service.documents().batchUpdate(
        documentId=document_id,
        body={"requests": requests}
    ).execute()

    return {
        "document_id": document_id,
        "updated": True,
        "mode": "append",
        "reply": result.get("replies", []),
    }


@mcp.tool()
def replace_document_text(document_id: str, text: str) -> dict[str, Any]:
    docs_service = get_docs_service()
    doc = docs_service.documents().get(documentId=document_id).execute()

    content = doc.get("body", {}).get("content", [])
    end_index = content[-1].get("endIndex", 1)

    requests = []

    if end_index > 2:
        requests.append({
            "deleteContentRange": {
                "range": {
                    "startIndex": 1,
                    "endIndex": end_index - 1
                }
            }
        })

    requests.append({
        "insertText": {
            "location": {"index": 1},
            "text": text
        }
    })

    result = docs_service.documents().batchUpdate(
        documentId=document_id,
        body={"requests": requests}
    ).execute()

    return {
        "document_id": document_id,
        "updated": True,
        "mode": "replace",
        "reply": result.get("replies", []),
    }


@mcp.tool()
def search_drive_files(
    query: str = "",
    mime_type: Optional[str] = None,
    parent_folder_id: Optional[str] = None,
    page_size: int = 10
) -> dict[str, Any]:
    drive_service = get_drive_service()

    conditions = ["trashed = false"]

    if query:
        escaped = query.replace("'", "\\'")
        conditions.append(f"name contains '{escaped}'")

    if mime_type:
        conditions.append(f"mimeType = '{mime_type}'")

    if parent_folder_id:
        conditions.append(f"'{parent_folder_id}' in parents")

    q = " and ".join(conditions)

    result = drive_service.files().list(
        q=q,
        pageSize=page_size,
        fields="files(id, name, mimeType, parents, webViewLink, createdTime, modifiedTime)"
    ).execute()

    return {
        "count": len(result.get("files", [])),
        "files": result.get("files", []),
    }


@mcp.tool()
def list_folder_files(folder_id: str, page_size: int = 20) -> dict[str, Any]:
    drive_service = get_drive_service()

    result = drive_service.files().list(
        q=f"'{folder_id}' in parents and trashed = false",
        pageSize=page_size,
        fields="files(id, name, mimeType, parents, webViewLink, createdTime, modifiedTime)"
    ).execute()

    return {
        "folder_id": folder_id,
        "count": len(result.get("files", [])),
        "files": result.get("files", []),
    }


@mcp.tool()
def create_folder(name: str, parent_folder_id: Optional[str] = None) -> dict[str, Any]:
    drive_service = get_drive_service()

    body = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }

    if parent_folder_id:
        body["parents"] = [parent_folder_id]

    folder = drive_service.files().create(
        body=body,
        fields="id, name, mimeType, parents, webViewLink"
    ).execute()

    return folder


@mcp.tool()
def move_file(file_id: str, new_parent_folder_id: str) -> dict[str, Any]:
    drive_service = get_drive_service()

    current_file = drive_service.files().get(
        fileId=file_id,
        fields="id, name, parents"
    ).execute()

    previous_parents = ",".join(current_file.get("parents", []))

    updated = drive_service.files().update(
        fileId=file_id,
        addParents=new_parent_folder_id,
        removeParents=previous_parents,
        fields="id, name, parents, webViewLink"
    ).execute()

    return updated


@mcp.tool()
def share_file(
    file_id: str,
    email: str,
    role: str = "writer",
    send_notification_email: bool = False
) -> dict[str, Any]:
    drive_service = get_drive_service()

    permission_body = {
        "type": "user",
        "role": role,
        "emailAddress": email,
    }

    permission = drive_service.permissions().create(
        fileId=file_id,
        body=permission_body,
        sendNotificationEmail=send_notification_email,
        fields="id, type, role, emailAddress"
    ).execute()

    return {
        "file_id": file_id,
        "permission": permission,
    }


@mcp.tool()
def get_file_metadata(file_id: str) -> dict[str, Any]:
    drive_service = get_drive_service()

    file_meta = drive_service.files().get(
        fileId=file_id,
        fields="id, name, mimeType, parents, webViewLink, createdTime, modifiedTime, owners"
    ).execute()

    return file_meta


@mcp.custom_route("/healthz", methods=["GET"], include_in_schema=False)
async def healthz(_: Request):
    return JSONResponse({"name": "google_docs", "status": "ok"})


@mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
async def health(_: Request):
    return JSONResponse({"status": "ok", "server": "google-docs-drive-mcp"})


if __name__ == "__main__":
    transport = os.getenv("FASTMCP_TRANSPORT", "streamable-http")
    host = os.getenv("FASTMCP_HOST", "0.0.0.0")
    port = int(os.getenv("FASTMCP_PORT", os.getenv("PORT", "8001")))
    mcp.run(transport=transport, host=host, port=port)
