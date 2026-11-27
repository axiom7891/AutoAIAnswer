from __future__ import annotations

import socket
import threading
import time

import uvicorn

from ai_screenshot_assistant.backend.app import app
from ai_screenshot_assistant.utils.network import get_lan_ip

CANDIDATE_COUNT = 10


def _port_free(port: int) -> bool:
    """能否在 0.0.0.0:port 上监听（先探测是否已有人在监听）。"""
    probe_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe_conn.settimeout(0.2)
    try:
        probe_conn.connect(("127.0.0.1", port))
        return False
    except OSError:
        pass
    finally:
        probe_conn.close()

    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("0.0.0.0", port))
        return True
    except OSError:
        return False
    finally:
        probe.close()


class EmbeddedBackend:
    def __init__(self, preferred_port: int, *, candidates: int = CANDIDATE_COUNT) -> None:
        # 默认仍从固定端口开始，端口被占用时依次尝试 +1，避免直接启动失败。
        self.preferred_port = int(preferred_port)
        self.candidates = max(1, int(candidates))
        self.port = self.preferred_port
        self.lan_ip = get_lan_ip()
        self.url = f"http://{self.lan_ip}:{self.port}"
        self.local_url = f"http://127.0.0.1:{self.port}"
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self.attempts: list[tuple[int, str]] = []

    def _configure(self, port: int) -> None:
        self.port = port
        self.url = f"http://{self.lan_ip}:{port}"
        self.local_url = f"http://127.0.0.1:{port}"
        self._server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="0.0.0.0",
                port=port,
                log_level="warning",
                use_colors=False,
                ws_max_size=64 * 1024 * 1024,
            )
        )
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def _wait_ready(self, timeout: float = 10.0) -> bool:
        assert self._server is not None and self._thread is not None
        deadline = time.monotonic() + timeout
        while not self._server.started and self._thread.is_alive():
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.05)
        return bool(self._server.started)

    def start(self) -> str:
        last_error = ""
        for offset in range(self.candidates):
            port = self.preferred_port + offset
            if not _port_free(port):
                self.attempts.append((port, "端口被占用"))
                last_error = f"端口 {port} 已被占用"
                continue
            self._configure(port)
            try:
                self._thread.start()  # type: ignore[union-attr]
            except Exception as exc:  # pragma: no cover - 极少见
                self.attempts.append((port, str(exc)))
                last_error = str(exc)
                continue
            if self._wait_ready():
                return self.url
            self.attempts.append((port, "后端启动失败"))
            last_error = f"端口 {port} 上后端启动失败"
            self.stop()

        tried = "、".join(str(self.preferred_port + i) for i in range(self.candidates))
        raise RuntimeError(f"本地服务启动失败（已尝试端口 {tried}）：{last_error or '未知原因'}")

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5)
