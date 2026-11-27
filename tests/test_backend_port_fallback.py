from __future__ import annotations

import socket

import pytest

from ai_screenshot_assistant.backend.embedded import EmbeddedBackend, _port_free


def _listen() -> tuple[socket.socket, int]:
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.bind(("0.0.0.0", 0))
    holder.listen(1)
    return holder, holder.getsockname()[1]


def test_port_free_detects_real_listener() -> None:
    holder, port = _listen()
    try:
        assert _port_free(port) is False
    finally:
        holder.close()


def test_port_free_true_for_unused_port() -> None:
    holder, port = _listen()
    holder.close()

    assert _port_free(port) is True


def test_backend_falls_back_when_port_busy() -> None:
    holder, port = _listen()
    backend = EmbeddedBackend(port, candidates=5)
    try:
        url = backend.start()

        assert backend.port != port
        assert url.endswith(f":{backend.port}")
        assert backend.attempts and backend.attempts[0][0] == port
    finally:
        backend.stop()
        holder.close()


def test_backend_reports_when_all_ports_busy() -> None:
    holder, port = _listen()
    second = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    second.bind(("0.0.0.0", port + 1))
    second.listen(1)
    backend = EmbeddedBackend(port, candidates=2)
    try:
        with pytest.raises(RuntimeError) as excinfo:
            backend.start()
        assert "启动失败" in str(excinfo.value)
    finally:
        backend.stop()
        holder.close()
        second.close()
