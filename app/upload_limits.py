"""Enforce upload stream limits before multipart parsing can spool arbitrary data."""

from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse


class DocumentUploadLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or not path.endswith("/documents/upload")
        ):
            return await self.app(scope, receive, send)
        limit = 41 * 1024 * 1024
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
                    {"detail": "Document upload request exceeds 41 MB"},
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
                    raise HTTPException(413, "Document upload request exceeds 41 MB")
            return message

        await self.app(scope, bounded_receive, send)
