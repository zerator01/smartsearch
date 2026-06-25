import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any

import httpx


BROWSER_ERROR_MARKERS = (
    "server not found",
    "we're having trouble finding that site",
    "we can’t connect to the server",
    "we can't connect to the server",
    "dns_probe_finished",
    "this site can’t be reached",
    "this site can't be reached",
)


def _elapsed_ms(start: float) -> float:
    return round((time.time() - start) * 1000, 2)


async def _run_command(args: list[str], timeout: float = 20.0) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    return proc.returncode or 0, stdout.decode("utf-8", "replace"), stderr.decode("utf-8", "replace")


async def _run_shell(command: str, timeout: float = 20.0) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    return proc.returncode or 0, stdout.decode("utf-8", "replace"), stderr.decode("utf-8", "replace")


def _parse_mcp_payload(text: str) -> dict[str, Any]:
    payload: dict[str, Any] | None = None
    for line in text.splitlines():
        if line.startswith("data: "):
            data = line[6:].strip()
            if data and data != "[DONE]":
                payload = json.loads(data)
    if payload is not None:
        return payload
    return json.loads(text)


def _mcp_text(result: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in result.get("content", []) or []:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text", "")))
        elif isinstance(item, dict) and item.get("text"):
            parts.append(str(item.get("text", "")))
    return "\n".join(part for part in parts if part)


def _extract_tab_id(result: dict[str, Any]) -> str:
    structured = result.get("structuredContent") if isinstance(result.get("structuredContent"), dict) else {}
    for key in ("tabId", "tab_id", "targetId"):
        value = structured.get(key)
        if value:
            return str(value)
    text = _mcp_text(result)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            for key in ("tabId", "tab_id", "targetId"):
                if parsed.get(key):
                    return str(parsed[key])
    except Exception:
        pass
    match = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", text, re.I)
    return match.group(0) if match else ""


def _looks_like_browser_error(snapshot: str) -> bool:
    lower = snapshot.lower()
    return any(marker in lower for marker in BROWSER_ERROR_MARKERS)


class CamofoxBrowserProvider:
    def __init__(
        self,
        *,
        mcp_url: str,
        health_url: str,
        auth_token: str = "",
        token_command: str = "",
        tunnel_script: str = "",
        ssh_host: str = "",
        timeout: float = 75.0,
        enabled: bool = True,
    ):
        self.mcp_url = mcp_url
        self.health_url = health_url
        self.auth_token = auth_token
        self.token_command = token_command
        self.tunnel_script = tunnel_script
        self.ssh_host = ssh_host
        self.timeout = timeout
        self.enabled = enabled

    def configured(self) -> bool:
        if not self.enabled:
            return False
        return bool(
            self.auth_token
            or self.token_command
            or (self.tunnel_script and Path(self.tunnel_script).exists())
        )

    async def ensure_tunnel(self) -> dict[str, Any]:
        if not self.tunnel_script or not Path(self.tunnel_script).exists():
            return {"ok": True, "status": "skipped", "message": "CAMOFOX_TUNNEL_SCRIPT is not configured or does not exist"}
        try:
            code, _, stderr = await _run_command([self.tunnel_script, "ensure"], timeout=25.0)
            return {"ok": code == 0, "status": "ok" if code == 0 else "error", "message": stderr.strip()[:500]}
        except Exception as exc:
            return {"ok": False, "status": "error", "message": str(exc)}

    async def resolve_token(self) -> str:
        if self.auth_token:
            return self.auth_token
        if self.token_command:
            code, stdout, _ = await _run_shell(self.token_command, timeout=20.0)
            return stdout.strip() if code == 0 and stdout.strip() else ""
        if self.ssh_host:
            remote_cmd = 'docker exec "$(docker ps -q --filter name=camofox-mcp-bridge | head -n1)" sh -lc \'printf %s "$BRIDGE_ACCESS_KEY"\''
            code, stdout, _ = await _run_command(
                ["ssh", "-n", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", self.ssh_host, remote_cmd],
                timeout=20.0,
            )
            return stdout.strip() if code == 0 and stdout.strip() else ""
        return ""

    async def call_mcp(self, method: str, params: dict[str, Any], token: str, timeout: float | None = None) -> dict[str, Any]:
        payload = {"jsonrpc": "2.0", "id": int(time.time() * 1000) % 1000000000, "method": method, "params": params}
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        async with httpx.AsyncClient(timeout=timeout or self.timeout) as client:
            response = await client.post(self.mcp_url, headers=headers, json=payload)
            response.raise_for_status()
        data = _parse_mcp_payload(response.text)
        if data.get("error"):
            raise RuntimeError(data["error"])
        return data.get("result", {})

    async def call_tool(self, name: str, arguments: dict[str, Any], token: str, timeout: float | None = None) -> dict[str, Any]:
        return await self.call_mcp("tools/call", {"name": name, "arguments": arguments}, token, timeout=timeout)

    async def health(self) -> dict[str, Any]:
        start = time.time()
        if not self.enabled:
            return {"status": "disabled", "message": "CAMOFOX_BROWSER_FETCH_ENABLED=false", "response_time_ms": _elapsed_ms(start)}
        await self.ensure_tunnel()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.health_url)
                response.raise_for_status()
        except Exception as exc:
            return {"status": "browser_unavailable", "message": f"Camofox health check failed: {exc}", "response_time_ms": _elapsed_ms(start)}
        try:
            token = await self.resolve_token()
        except Exception as exc:
            return {"status": "auth_error", "message": f"Camofox token resolution failed: {exc}", "response_time_ms": _elapsed_ms(start)}
        if not token:
            return {"status": "auth_error", "message": "Camofox auth token is not available", "response_time_ms": _elapsed_ms(start)}
        return {"status": "ok", "message": "Camofox browser bridge is available", "response_time_ms": _elapsed_ms(start)}

    async def fetch(self, url: str) -> str:
        start = time.time()
        if not self.enabled:
            return json.dumps(
                {
                    "ok": False,
                    "provider": "camofox-browser",
                    "url": url,
                    "content": "",
                    "error_type": "config_error",
                    "error": "CAMOFOX_BROWSER_FETCH_ENABLED=false",
                    "elapsed_ms": _elapsed_ms(start),
                },
                ensure_ascii=False,
                indent=2,
            )

        await self.ensure_tunnel()
        try:
            health = await self.health()
            if health.get("status") != "ok":
                return json.dumps(
                    {
                        "ok": False,
                        "provider": "camofox-browser",
                        "url": url,
                        "content": "",
                        "error_type": health.get("status") or "browser_unavailable",
                        "error": health.get("message") or "Camofox browser bridge is unavailable",
                        "elapsed_ms": _elapsed_ms(start),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            token = await self.resolve_token()
        except Exception as exc:
            return json.dumps(
                {
                    "ok": False,
                    "provider": "camofox-browser",
                    "url": url,
                    "content": "",
                    "error_type": "auth_error",
                    "error": f"Camofox setup failed: {exc}",
                    "elapsed_ms": _elapsed_ms(start),
                },
                ensure_ascii=False,
                indent=2,
            )

        tab_id = ""
        metadata: dict[str, Any] = {"fetch_method": "accessibility_snapshot"}
        try:
            await self.call_mcp(
                "initialize",
                {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "smart-search", "version": "0.1.14"},
                },
                token,
                timeout=15.0,
            )
            created = await self.call_tool("create_tab", {"session_key": "smart-search-browser-fetch"}, token, timeout=30.0)
            tab_id = _extract_tab_id(created)
            if not tab_id:
                return json.dumps(
                    {
                        "ok": False,
                        "provider": "camofox-browser",
                        "url": url,
                        "content": "",
                        "error_type": "browser_fetch_error",
                        "error": "Camofox did not return a tab id",
                        "metadata": metadata,
                        "elapsed_ms": _elapsed_ms(start),
                    },
                    ensure_ascii=False,
                    indent=2,
                )

            await self.call_tool("navigate", {"tab_id": tab_id, "url": url}, token, timeout=self.timeout)
            snapshot_result = await self.call_tool(
                "snapshot",
                {"tab_id": tab_id, "format": "text", "include_screenshot": False, "offset": 0},
                token,
                timeout=self.timeout,
            )
            content = _mcp_text(snapshot_result).strip()
            metadata["snapshot_chars"] = len(content)
            if content and not _looks_like_browser_error(content):
                return json.dumps(
                    {
                        "ok": True,
                        "provider": "camofox-browser",
                        "url": url,
                        "content": content,
                        "content_format": "accessibility_snapshot",
                        "metadata": metadata,
                        "elapsed_ms": _elapsed_ms(start),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            return json.dumps(
                {
                    "ok": False,
                    "provider": "camofox-browser",
                    "url": url,
                    "content": "",
                    "error_type": "browser_navigation_error",
                    "error": content[:500] if content else "Camofox returned an empty snapshot",
                    "metadata": metadata,
                    "elapsed_ms": _elapsed_ms(start),
                },
                ensure_ascii=False,
                indent=2,
            )
        except Exception as exc:
            return json.dumps(
                {
                    "ok": False,
                    "provider": "camofox-browser",
                    "url": url,
                    "content": "",
                    "error_type": "browser_fetch_error",
                    "error": str(exc),
                    "metadata": metadata,
                    "elapsed_ms": _elapsed_ms(start),
                },
                ensure_ascii=False,
                indent=2,
            )
        finally:
            if tab_id:
                try:
                    await self.call_tool("close_tab", {"tab_id": tab_id}, token, timeout=20.0)
                except Exception:
                    pass
