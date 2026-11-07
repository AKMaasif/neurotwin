"""Enforce upload stream limits before multipart parsing can spool arbitrary data."""

from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse


class DocumentUploadLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope["type"] != "http" or scope.get("method") not in {"POST", "PATCH"}:
            return await self.app(scope, receive, send)
        if path == "/api/account/password":
            limit, label = 16 * 1024, "Password-change request exceeds 16 KB"
        elif path.endswith("/camera/check"):
            limit, label = 1024 * 1024, "Camera sample exceeds 1 MB"
        elif scope.get("method") == "PATCH" and "/messages/uploads/" in path:
            limit, label = 1024 * 1024, "Upload chunk exceeds 1 MB"
        elif path.endswith("/documents/upload"):
            limit, label = 41 * 1024 * 1024, "Document upload request exceeds 41 MB"
        elif "/messages/threads/" in path and path.endswith("/voice"):
            limit, label = (
                2 * 1024 * 1024 + 65536,
                "Voice-note request exceeds allowed size",
            )
        else:
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        if b"content-length" in headers:
            try:
                length = int(headers[b"content-length"])
            except ValueError:
                return await JSONResponse(
                    {"detail": "Invalid content length"}, status_code=400
                )(scope, receive, send)
            if length < 0 or length > limit:
                return await JSONResponse(
                    {"detail": label},
                    status_code=413,
                    headers={"Cache-Control": "no-store"},
                )(scope, receive, send)
        count = 0

        async def bounded_receive():
            nonlocal count
            message = await receive()
            if message["type"] == "http.request":
                count += len(message.get("body", b""))
                if count > limit:
                    raise HTTPException(413, label)
            return message

        await self.app(scope, bounded_receive, send)
