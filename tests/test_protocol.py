"""Protocol validator tests.

These exercise the lightweight validators without touching Playwright or the
network — they are the first line of defence at the API boundary.
"""

import pytest

from anxbrowser.protocol import (
    ProtocolError,
    validate_click,
    validate_create_session,
    validate_eval,
    validate_navigate,
    validate_observe,
    validate_scroll,
    validate_type,
    validate_wait_for,
)


class TestCreateSession:
    def test_defaults(self):
        out = validate_create_session({})
        assert out["headless"] is True
        assert out["viewport"] == {"width": 1280, "height": 800}
        assert out["browser_engine"] == "chromium"
        assert out["dom_snapshot_mode"] == "light"
        assert out["dom_text_max_chars"] == 4096
        assert out["namespace"] == "/sessions"
        assert out["record"] is False

    def test_custom_viewport(self):
        out = validate_create_session({"viewport": {"width": 800, "height": 600}})
        assert out["viewport"] == {"width": 800, "height": 600}

    def test_invalid_viewport(self):
        with pytest.raises(ProtocolError):
            validate_create_session({"viewport": {"width": "big", "height": 600}})

    def test_invalid_browser_engine(self):
        with pytest.raises(ProtocolError):
            validate_create_session({"browser_engine": "webkit"})

    def test_invalid_dom_snapshot_mode(self):
        with pytest.raises(ProtocolError):
            validate_create_session({"dom_snapshot_mode": "raw"})

    def test_invalid_dom_text_limit(self):
        with pytest.raises(ProtocolError):
            validate_create_session({"dom_text_max_chars": 32})


class TestNavigate:
    def test_minimum(self):
        out = validate_navigate({"url": "https://example.com"})
        assert out["wait_until"] == "load"

    def test_missing_url(self):
        with pytest.raises(ProtocolError):
            validate_navigate({})

    def test_empty_url(self):
        with pytest.raises(ProtocolError):
            validate_navigate({"url": "   "})

    def test_bad_wait_until(self):
        with pytest.raises(ProtocolError):
            validate_navigate({"url": "https://x", "wait_until": "never"})


class TestClick:
    def test_defaults(self):
        out = validate_click({"selector": "#go"})
        assert out["button"] == "left"
        assert out["timeout_ms"] == 5000

    def test_bad_button(self):
        with pytest.raises(ProtocolError):
            validate_click({"selector": "#go", "button": "bottom"})


class TestType:
    def test_only_text(self):
        out = validate_type({"text": "hi"})
        assert out["selector"] is None
        assert out["press_enter"] is False

    def test_missing_text(self):
        with pytest.raises(ProtocolError):
            validate_type({"selector": "input"})


class TestScroll:
    def test_dy(self):
        assert validate_scroll({"dy": 300})["dy"] == 300

    def test_to_selector(self):
        assert validate_scroll({"to_selector": "#foot"})["to_selector"] == "#foot"


class TestWaitFor:
    def test_ok(self):
        out = validate_wait_for({"selector": "main", "timeout_ms": 5000})
        assert out["timeout_ms"] == 5000

    def test_missing(self):
        with pytest.raises(ProtocolError):
            validate_wait_for({})


class TestObserve:
    def test_defaults(self):
        out = validate_observe({})
        assert out["include_screenshot"] is True
        assert out["include_html"] is False
        assert out["text_only"] is True


class TestEval:
    def test_ok(self):
        out = validate_eval({"expression": "1+1"})
        assert out["expression"] == "1+1"

    def test_missing(self):
        with pytest.raises(ProtocolError):
            validate_eval({})
