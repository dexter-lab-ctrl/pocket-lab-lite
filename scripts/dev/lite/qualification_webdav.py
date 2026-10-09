#!/usr/bin/env python3
"""HTTPS WebDAV fixture owned by one disposable qualification run."""
from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import Response, StreamingResponse
import uvicorn


PREFIX = "apps/photoprism/originals"
_STATE_LOCK = threading.RLock()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_path(root: Path, raw: str) -> tuple[Path, str]:
    decoded = unquote(str(raw or "")).replace("\\", "/").lstrip("/")
    if decoded == PREFIX:
        relative = ""
    elif decoded.startswith(PREFIX + "/"):
        relative = decoded[len(PREFIX) + 1 :]
    else:
        raise ValueError("outside fixture namespace")
    parts = Path(relative).parts
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("invalid fixture path")
    target = (root / relative).resolve(strict=False)
    root_real = root.resolve(strict=True)
    if os.path.commonpath((str(target), str(root_real))) != str(root_real):
        raise ValueError("fixture path escaped root")
    current = root_real
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("fixture symlink path rejected")
    return target, relative


def _xml_metadata(relative: str, size: int, modified: str, *, directory: bool = False) -> bytes:
    name = Path(relative).name
    resource_type = "<D:collection/>" if directory else ""
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<D:multistatus xmlns:D="DAV:">'
        '<D:response><D:href>/' + PREFIX + "/" + relative + '</D:href>'
        f'<D:propstat><D:prop><D:resourcetype>{resource_type}</D:resourcetype>'
        f"<D:getcontentlength>{size}</D:getcontentlength>"
        f"<D:getlastmodified>{modified}</D:getlastmodified>"
        '</D:prop><D:status>HTTP/1.1 200 OK</D:status></D:propstat>'
        '</D:response></D:multistatus>'
    ).encode("utf-8")


def _basic(request: Request, expected_user: str, expected_password: str) -> bool:
    raw = str(request.headers.get("authorization") or "")
    if not raw.lower().startswith("basic "):
        return False
    try:
        user, password = base64.b64decode(raw.split(" ", 1)[1]).decode("utf-8").split(":", 1)
    except Exception:
        return False
    return secrets.compare_digest(user, expected_user) and secrets.compare_digest(password, expected_password)


def build_app(root: Path, user: str, password: str, control_token: str) -> FastAPI:
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root.chmod(0o700)
    state_path = root.parent / "webdav-state.json"
    fault_path = root.parent / "webdav-faults.json"
    lock = _STATE_LOCK

    def read_json(path: Path, default: dict) -> dict:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else default
        except (FileNotFoundError, OSError, ValueError):
            return default

    def write_json(path: Path, data: dict) -> None:
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(path)

    def record(operation: str, status: int) -> None:
        with lock:
            state = read_json(state_path, {"schema_version": 1, "requests": 0, "operations": {}})
            state["requests"] = int(state.get("requests") or 0) + 1
            operations = state.setdefault("operations", {})
            entry = operations.setdefault(operation, {"count": 0, "last_status": 0})
            entry["count"] = int(entry.get("count") or 0) + 1
            entry["last_status"] = int(status)
            entry["checked_at"] = _now()
            write_json(state_path, state)

    def maybe_fault(operation: str) -> Response | None:
        with lock:
            fault = read_json(fault_path, {})
            if str(fault.get("operation") or "") not in {operation, "*"}:
                return None
            remaining = int(fault.get("remaining") or 0)
            if remaining <= 0:
                return None
            fault["remaining"] = remaining - 1
            write_json(fault_path, fault)
        status = int(fault.get("status") or 503)
        record(operation, status)
        if status == 401:
            return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="qualification"'})
        return Response(status_code=max(400, min(status, 599)))

    def authorized(request: Request) -> bool:
        return _basic(request, user, password)

    app = FastAPI(title="Pocket Lab isolated WebDAV fixture", docs_url=None, redoc_url=None)

    @app.get("/__qualification__/summary")
    async def summary(request: Request) -> Response:
        if request.headers.get("x-qualification-control") != control_token:
            return Response(status_code=404)
        with lock:
            state = read_json(state_path, {"schema_version": 1, "requests": 0, "operations": {}})
            files = 0
            total_bytes = 0
            for path in root.rglob("*"):
                if path.is_file() and not path.is_symlink():
                    files += 1
                    total_bytes += path.stat().st_size
        return Response(
            content=json.dumps({"schema_version": 1, "files": files, "bytes": total_bytes, "state": state, "sanitized": True}),
            media_type="application/json",
        )

    @app.post("/__qualification__/fault")
    async def fault(request: Request) -> Response:
        if request.headers.get("x-qualification-control") != control_token:
            return Response(status_code=404)
        try:
            payload = await request.json()
            operation = str(payload.get("operation") or "*")
            status = int(payload.get("status") or 503)
            remaining = int(payload.get("remaining") or 0)
        except Exception:
            return Response(status_code=400)
        if operation not in {"OPTIONS", "PROPFIND", "PUT", "MOVE", "DELETE", "GET", "*"} or status < 400 or status > 599 or not 0 <= remaining <= 100:
            return Response(status_code=422)
        with lock:
            write_json(fault_path, {"operation": operation, "status": status, "remaining": remaining})
        return Response(content=json.dumps({"status": "armed", "sanitized": True}), media_type="application/json")

    @app.api_route("/{path:path}", methods=["OPTIONS", "PROPFIND", "PUT", "MOVE", "DELETE", "GET", "HEAD"])
    async def webdav(request: Request, path: str) -> Response:
        operation = request.method.upper()
        fault = maybe_fault(operation)
        if fault is not None:
            return fault
        if not authorized(request):
            record(operation, 401)
            return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="qualification"'})
        try:
            target, relative = _safe_path(root, path)
        except ValueError:
            record(operation, 404)
            return Response(status_code=404)
        if operation == "OPTIONS":
            record(operation, 200)
            return Response(status_code=200, headers={"Allow": "OPTIONS, PROPFIND, PUT, MOVE, DELETE, GET, HEAD", "DAV": "1,2"})
        if operation == "PROPFIND":
            if relative == "" and target.is_dir():
                record(operation, 207)
                return Response(content=_xml_metadata("", 0, _now(), directory=True), status_code=207, media_type="application/xml", headers={"DAV": "1,2"})
            if not target.is_file() or target.is_symlink():
                record(operation, 404)
                return Response(status_code=404)
            record(operation, 207)
            return Response(content=_xml_metadata(relative, target.stat().st_size, _now()), status_code=207, media_type="application/xml", headers={"DAV": "1,2"})
        if operation == "PUT":
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            data = await request.body()
            temporary = target.with_name(f".{target.name}.{os.getpid()}.upload")
            temporary.write_bytes(data)
            temporary.chmod(0o600)
            temporary.replace(target)
            record(operation, 201)
            return Response(status_code=201)
        if operation == "MOVE":
            destination = str(request.headers.get("destination") or "")
            parsed = urlsplit(destination)
            try:
                target_destination, _ = _safe_path(root, parsed.path)
            except ValueError:
                record(operation, 409)
                return Response(status_code=409)
            if not target.is_file() or target.is_symlink():
                record(operation, 404)
                return Response(status_code=404)
            target_destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            target.replace(target_destination)
            record(operation, 201)
            return Response(status_code=201)
        if operation == "DELETE":
            if not target.is_file() or target.is_symlink():
                record(operation, 404)
                return Response(status_code=404)
            target.unlink()
            record(operation, 204)
            return Response(status_code=204)
        if operation in {"GET", "HEAD"}:
            if not target.is_file() or target.is_symlink():
                record(operation, 404)
                return Response(status_code=404)
            record(operation, 200)
            if operation == "HEAD":
                return Response(status_code=200, headers={"Content-Length": str(target.stat().st_size)})
            return StreamingResponse(open(target, "rb"), media_type="application/octet-stream", headers={"Content-Length": str(target.stat().st_size)})
        record(operation, 405)
        return Response(status_code=405)

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--root", required=True)
    parser.add_argument("--user", default=os.environ.get("QUALIFICATION_WEBDAV_USER", "qualification"))
    parser.add_argument("--password", default=os.environ.get("QUALIFICATION_WEBDAV_PASSWORD", ""))
    parser.add_argument("--control-token", default=os.environ.get("QUALIFICATION_CONTROL_TOKEN", ""))
    parser.add_argument("--ssl-keyfile", required=True)
    parser.add_argument("--ssl-certfile", required=True)
    args = parser.parse_args(argv)
    if not args.serve:
        parser.error("--serve is required")
    if not args.password or not args.control_token:
        parser.error("qualification fixture credentials must be supplied through its environment")
    uvicorn.run(
        build_app(Path(args.root), args.user, args.password, args.control_token),
        host=args.host,
        port=args.port,
        ssl_keyfile=args.ssl_keyfile,
        ssl_certfile=args.ssl_certfile,
        log_level="warning",
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
