"""Capability parsing tests."""

import base64
import json

import pytest

from anxbrowser.capability import Capability, parse_header, require_verbs, synthetic


def _make_header(payload: dict) -> str:
    raw = json.dumps(payload).encode("utf-8")
    b64 = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    return f"ANX-Capability {b64}"


def test_parse_none_returns_none():
    assert parse_header(None) is None


def test_parse_wellformed_token():
    cap = parse_header(_make_header({"actor": "agent:x", "verbs": ["navigate"]}))
    assert cap is not None
    assert cap.actor == "agent:x"
    assert cap.allows("navigate")
    assert not cap.allows("eval")


def test_parse_wildcard_verb():
    cap = parse_header(_make_header({"actor": "a", "verbs": ["*"]}))
    assert cap.allows("anything")


def test_parse_bad_scheme_raises():
    with pytest.raises(ValueError):
        parse_header("Bearer foo")


def test_parse_garbage_raises():
    with pytest.raises(ValueError):
        parse_header("ANX-Capability !not-b64-json!")


def test_synthetic_grants_all_known():
    cap = synthetic()
    assert cap.allows("navigate")
    assert cap.allows("click")
    assert cap.allows("eval")


def test_require_verbs_passes_on_match():
    cap = Capability(actor="a", session=None, cell=None, verbs=["navigate", "click"])
    require_verbs(cap, ["navigate"])


def test_require_verbs_raises_on_miss():
    cap = Capability(actor="a", session=None, cell=None, verbs=["navigate"])
    with pytest.raises(PermissionError):
        require_verbs(cap, ["eval"])
