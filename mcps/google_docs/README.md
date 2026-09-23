# Google Docs + Drive MCP Server

FastMCP server for Google Docs document operations and Google Drive file/folder
operations. In this monorepo it runs as the `mcp-google-docs` service on port
`8001` and exposes the streamable HTTP MCP endpoint at `/mcp`.

## Tools

Google Docs:

- `create_document`
- `get_document`
- `append_to_document`
- `replace_document_text`

Google Drive:

- `search_drive_files`
- `list_folder_files`
- `create_folder`
- `move_file`
- `share_file`
- `get_file_metadata`

## Configuration

Only one local env file is required:

```bash
cp mcps/google_docs/.env.google_docs.example mcps/google_docs/.env.google_docs
```

Fill these values in `mcps/google_docs/.env.google_docs`:

```env
GOOGLE_DRIVE_DEFAULT_FOLDER_ID=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REFRESH_TOKEN=
```

`GOOGLE_DRIVE_DEFAULT_FOLDER_ID` is the Drive folder used by default when a new
Google Doc is created. For a folder URL like:

```text
https://drive.google.com/drive/folders/abc123
```

use:

```env
GOOGLE_DRIVE_DEFAULT_FOLDER_ID=abc123
```

## Refresh Token

Create a Google OAuth Desktop app in Google Cloud Console, then use OAuth
Playground once to get a refresh token:

1. Open `https://developers.google.com/oauthplayground`.
2. Click the gear icon and enable `Use your own OAuth credentials`.
3. Enter `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.
4. Select these scopes:
   - `https://www.googleapis.com/auth/documents`
   - `https://www.googleapis.com/auth/drive`
5. Click `Authorize APIs`, sign in, and approve access.
6. Click `Exchange authorization code for tokens`.
7. Copy the `refresh_token` into `GOOGLE_REFRESH_TOKEN`.

## Local Run

From the repository root:

```bash
docker compose up --build mcp-google-docs
```

Health checks:

```text
http://localhost:8001/healthz
http://localhost:8001/health
```
