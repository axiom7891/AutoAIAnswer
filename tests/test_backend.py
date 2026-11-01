from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from ai_screenshot_assistant.backend.app import app
from ai_screenshot_assistant.backend.session_manager import MAX_SESSION_EVENTS, MAX_STORED_TEXT_CHARS, SessionManager


def test_create_session_and_mobile_page() -> None:
    client = TestClient(app)

    response = client.post("/sessions")
    assert response.status_code == 200
    session = response.json()

    page = client.get(session["pair_url"])
    assert page.status_code == 200
    assert session["session_id"] in page.text


def test_mobile_static_assets_are_served_with_expected_content_types() -> None:
    client = TestClient(app)

    css = client.get("/static/style.css?v=0.2.58")
    js = client.get("/static/app.js?v=0.2.58")

    assert css.status_code == 200
    assert css.headers["content-type"].startswith("text/css")
    assert b"--background" in css.content
    assert js.status_code == 200
    assert js.headers["content-type"].split(";", 1)[0] in {"application/javascript", "text/javascript"}
    assert b"function connect" in js.content


def test_create_session_reuses_requested_pair_token() -> None:
    client = TestClient(app)
    token = "stable_pair_token_1234567890"

    first = client.post("/sessions", json={"pair_token": token}).json()
    second = client.post("/sessions", json={"pair_token": token}).json()

    assert first["pair_url"] == second["pair_url"] == f"/pair?t={token}"
    assert first["session_id"] != second["session_id"]
    assert client.get(first["mobile_url"]).status_code == 404
    assert client.get(second["pair_url"]).status_code == 200


def test_create_session_rejects_weak_requested_pair_token() -> None:
    client = TestClient(app)

    session = client.post("/sessions", json={"pair_token": "too-short"}).json()

    assert session["pair_token"] != "too-short"
    assert len(session["pair_token"]) >= 24


def test_active_desktop_keeps_stable_pair_session_alive() -> None:
    local_manager = SessionManager()
    session = local_manager.create_session(ttl_minutes=1, pair_token="stable_pair_token_1234567890")
    session.desktop = object()
    session.expire_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    assert local_manager.get_by_token(session.pair_token) is session
    assert session.expire_at > datetime.now(timezone.utc)


def test_desktop_events_reach_mobile_websocket() -> None:
    client = TestClient(app)
    session = client.post("/sessions").json()
    session_id = session["session_id"]

    with client.websocket_connect(f"/ws/mobile/{session_id}") as mobile:
        mobile.receive_json()
        with client.websocket_connect(f"/ws/desktop/{session_id}") as desktop:
            mobile.receive_json()
            desktop.send_json(
                {
                    "type": "answer.delta",
                    "session_id": session_id,
                    "request_id": "r1",
                    "timestamp": "now",
                    "payload": {"delta": "B"},
                }
            )
            received = mobile.receive_json()

    assert received["type"] == "answer.delta"
    assert received["payload"]["delta"] == "B"
    assert received["event_id"] == 1


def test_scroll_command_from_desktop_reaches_mobile() -> None:
    client = TestClient(app)
    session = client.post("/sessions").json()
    session_id = session["session_id"]

    with client.websocket_connect(f"/ws/mobile/{session_id}") as mobile:
        mobile.receive_json()
        with client.websocket_connect(f"/ws/desktop/{session_id}") as desktop:
            mobile.receive_json()
            desktop.send_json(
                {
                    "type": "answer.scroll",
                    "session_id": session_id,
                    "timestamp": "now",
                    "payload": {"direction": "down", "steps": 1},
                }
            )
            received = mobile.receive_json()

    assert received["type"] == "answer.scroll"
    assert received["payload"]["direction"] == "down"


def test_mobile_fullscreen_command_reaches_desktop_command_socket() -> None:
    client = TestClient(app)
    session = client.post("/sessions").json()
    session_id = session["session_id"]

    with client.websocket_connect(f"/ws/desktop-commands/{session_id}") as desktop_commands:
        with client.websocket_connect(f"/ws/mobile/{session_id}") as mobile:
            mobile.receive_json()
            mobile.send_text('{"type":"command.fullscreen"}')
            command = desktop_commands.receive_json()

    assert command["type"] == "command.fullscreen"
    assert command["payload"] == {"source": "mobile"}


def test_mobile_fullscreen_command_forwards_question_payload() -> None:
    client = TestClient(app)
    session = client.post("/sessions").json()
    session_id = session["session_id"]

    with client.websocket_connect(f"/ws/desktop-commands/{session_id}") as desktop_commands:
        with client.websocket_connect(f"/ws/mobile/{session_id}") as mobile:
            mobile.receive_json()
            mobile.send_text(
                '{"type":"command.fullscreen","payload":{"text":"解释第 2 题","conversation":true}}'
            )
            command = desktop_commands.receive_json()

    assert command["type"] == "command.fullscreen"
    assert command["payload"] == {
        "source": "mobile",
        "text": "解释第 2 题",
        "conversation": True,
    }


def test_mobile_fullscreen_command_forwards_chat_payload() -> None:
    client = TestClient(app)
    session = client.post("/sessions").json()
    session_id = session["session_id"]

    with client.websocket_connect(f"/ws/desktop-commands/{session_id}") as desktop_commands:
        with client.websocket_connect(f"/ws/mobile/{session_id}") as mobile:
            mobile.receive_json()
            mobile.send_text(
                '{"type":"command.fullscreen","payload":{"text":"看一下这个空怎么填","conversation":true,"chat":true}}'
            )
            command = desktop_commands.receive_json()

    assert command["type"] == "command.fullscreen"
    assert command["payload"] == {
        "source": "mobile",
        "text": "看一下这个空怎么填",
        "conversation": True,
        "chat": True,
    }


def test_mobile_fullscreen_command_forwards_client_request_id() -> None:
    client = TestClient(app)
    session = client.post("/sessions").json()
    session_id = session["session_id"]

    with client.websocket_connect(f"/ws/desktop-commands/{session_id}") as desktop_commands:
        with client.websocket_connect(f"/ws/mobile/{session_id}") as mobile:
            mobile.receive_json()
            mobile.send_text(
                '{"type":"command.fullscreen","payload":{"client_request_id":"fullscreen-123"}}'
            )
            command = desktop_commands.receive_json()

    assert command["type"] == "command.fullscreen"
    assert command["payload"] == {
        "source": "mobile",
        "client_request_id": "fullscreen-123",
    }


def test_mobile_capture_fullscreen_command_reaches_desktop_command_socket() -> None:
    client = TestClient(app)
    session = client.post("/sessions").json()
    session_id = session["session_id"]

    with client.websocket_connect(f"/ws/desktop-commands/{session_id}") as desktop_commands:
        with client.websocket_connect(f"/ws/mobile/{session_id}") as mobile:
            mobile.receive_json()
            mobile.send_text('{"type":"command.capture_fullscreen"}')
            command = desktop_commands.receive_json()

    assert command["type"] == "command.capture_fullscreen"
    assert command["payload"] == {"source": "mobile"}


def test_mobile_submit_screenshots_forwards_images_without_text() -> None:
    client = TestClient(app)
    session = client.post("/sessions").json()
    session_id = session["session_id"]

    with client.websocket_connect(f"/ws/desktop-commands/{session_id}") as desktop_commands:
        with client.websocket_connect(f"/ws/mobile/{session_id}") as mobile:
            mobile.receive_json()
            mobile.send_text(
                '{"type":"command.submit_screenshots","payload":{"images":["img1","img2"],"conversation":true,"chat":true}}'
            )
            command = desktop_commands.receive_json()

    assert command["type"] == "command.submit_screenshots"
    assert command["payload"] == {
        "source": "mobile",
        "conversation": True,
        "chat": True,
        "images": ["img1", "img2"],
    }


def test_mobile_submit_screenshots_forwards_client_request_id() -> None:
    client = TestClient(app)
    session = client.post("/sessions").json()
    session_id = session["session_id"]

    with client.websocket_connect(f"/ws/desktop-commands/{session_id}") as desktop_commands:
        with client.websocket_connect(f"/ws/mobile/{session_id}") as mobile:
            mobile.receive_json()
            mobile.send_text(
                '{"type":"command.submit_screenshots","payload":{"text":"继续","client_request_id":"chat-456"}}'
            )
            command = desktop_commands.receive_json()

    assert command["type"] == "command.submit_screenshots"
    assert command["payload"] == {
        "source": "mobile",
        "text": "继续",
        "client_request_id": "chat-456",
    }


def test_mobile_submit_screenshots_forwards_screenshot_ids() -> None:
    client = TestClient(app)
    session = client.post("/sessions").json()
    session_id = session["session_id"]

    with client.websocket_connect(f"/ws/desktop-commands/{session_id}") as desktop_commands:
        with client.websocket_connect(f"/ws/mobile/{session_id}") as mobile:
            mobile.send_text(
                '{"type":"command.submit_screenshots","payload":{"images":["img1"],"screenshot_ids":["shot-1"],"chat":true}}'
            )
            command = desktop_commands.receive_json()

    assert command["type"] == "command.submit_screenshots"
    assert command["payload"]["screenshot_ids"] == ["shot-1"]


def test_session_events_are_bounded() -> None:
    manager = SessionManager()
    session = manager.create_session()

    for index in range(MAX_SESSION_EVENTS + 25):
        manager.append_event(session, {"type": "selection.status", "payload": {"state": str(index)}})

    assert len(session.events) == MAX_SESSION_EVENTS
    assert session.events[0]["event_id"] == 26
    assert session.events[-1]["event_id"] == MAX_SESSION_EVENTS + 25


def test_answer_deltas_are_not_persisted_in_session_history() -> None:
    manager = SessionManager()
    session = manager.create_session()

    live = manager.append_event(session, {"type": "answer.delta", "payload": {"delta": "A" * 5000}})

    assert live["event_id"] == 1
    assert live["payload"]["delta"].startswith("A")
    assert session.events == []


def test_screenshot_images_are_stripped_before_session_storage() -> None:
    manager = SessionManager()
    session = manager.create_session()

    live = manager.append_event(
        session,
        {"type": "screenshot.captured", "payload": {"image": "data:image/jpeg;base64,abc", "size": 12}},
    )

    assert live["payload"]["image"].startswith("data:image")
    assert session.events[0]["payload"]["image_omitted"] is True
    assert "image" not in session.events[0]["payload"]


def test_clear_events_releases_session_history() -> None:
    manager = SessionManager()
    session = manager.create_session()
    manager.append_event(session, {"type": "answer.completed", "payload": {"result": {"text": "答案"}}})

    manager.clear_events(session)

    assert session.events == []
    assert session.next_event_id == 2


def test_mobile_clear_conversation_command_reaches_desktop() -> None:
    client = TestClient(app)
    session = client.post("/sessions").json()
    session_id = session["session_id"]

    with client.websocket_connect(f"/ws/desktop-commands/{session_id}") as desktop_commands:
        with client.websocket_connect(f"/ws/mobile/{session_id}") as mobile:
            mobile.receive_json()
            mobile.send_text('{"type":"command.clear_conversation"}')
            command = desktop_commands.receive_json()

    assert command["type"] == "command.clear_conversation"
    assert command["payload"] == {"source": "mobile"}


def test_mobile_set_model_tier_command_forwards_tier() -> None:
    client = TestClient(app)
    session = client.post("/sessions").json()
    session_id = session["session_id"]

    with client.websocket_connect(f"/ws/desktop-commands/{session_id}") as desktop_commands:
        with client.websocket_connect(f"/ws/mobile/{session_id}") as mobile:
            mobile.receive_json()
            mobile.send_text('{"type":"command.set_model_tier","payload":{"tier":"openrouter-qwen-27b"}}')
            command = desktop_commands.receive_json()

    assert command["type"] == "command.set_model_tier"
    assert command["payload"]["source"] == "mobile"
    assert command["payload"]["tier"] == "openrouter-qwen-27b"
    assert command["payload"]["route"] == "openrouter-qwen-27b"


def test_two_mobile_clients_share_desktop_events() -> None:
    client = TestClient(app)
    session = client.post("/sessions").json()
    session_id = session["session_id"]

    def receive_type(websocket, event_type: str) -> dict:
        for _ in range(12):
            event = websocket.receive_json()
            if event["type"] == event_type:
                return event
        raise AssertionError(f"did not receive {event_type}")

    with client.websocket_connect(f"/ws/mobile/{session_id}") as first:
        with client.websocket_connect(f"/ws/mobile/{session_id}") as second:
            with client.websocket_connect(f"/ws/desktop/{session_id}") as desktop:
                desktop.send_json(
                    {
                        "type": "answer.delta",
                        "session_id": session_id,
                        "request_id": "shared-1",
                        "timestamp": "now",
                        "payload": {"delta": "共享答案"},
                    }
                )
                first_event = receive_type(first, "answer.delta")
                second_event = receive_type(second, "answer.delta")

    assert first_event["payload"]["delta"] == "共享答案"
    assert second_event["payload"]["delta"] == "共享答案"
    assert first_event["event_id"] == second_event["event_id"] == 1


def test_mobile_get_model_command_reaches_desktop() -> None:
    client = TestClient(app)
    session = client.post("/sessions").json()
    session_id = session["session_id"]

    with client.websocket_connect(f"/ws/desktop-commands/{session_id}") as desktop_commands:
        with client.websocket_connect(f"/ws/mobile/{session_id}") as mobile:
            mobile.send_text('{"type":"command.get_model"}')
            command = desktop_commands.receive_json()

    assert command["type"] == "command.get_model"
    assert command["payload"] == {"source": "mobile"}


def test_mobile_presence_reports_connected_devices() -> None:
    client = TestClient(app)
    session = client.post("/sessions").json()
    session_id = session["session_id"]

    with client.websocket_connect(f"/ws/mobile/{session_id}") as mobile:
        presence = mobile.receive_json()
        assert presence["type"] == "device.presence"
        assert presence["payload"] == {"desktop": False, "mobiles": 1}
        with client.websocket_connect(f"/ws/desktop/{session_id}") as _desktop:
            updated = None
            for _ in range(4):
                event = mobile.receive_json()
                if event["type"] == "device.presence":
                    updated = event
                    break
            assert updated is not None
            assert updated["payload"] == {"desktop": True, "mobiles": 1}


def test_completed_answer_text_is_truncated_in_session_storage() -> None:
    manager = SessionManager()
    session = manager.create_session()

    live = manager.append_event(
        session,
        {"type": "answer.completed", "payload": {"result": {"text": "答" * (MAX_STORED_TEXT_CHARS + 50)}}},
    )

    assert len(live["payload"]["result"]["text"]) == MAX_STORED_TEXT_CHARS + 50
    assert len(session.events[0]["payload"]["result"]["text"]) == MAX_STORED_TEXT_CHARS
