"""Config tests."""

import os
from unittest import mock

from anxbrowser.config import Config


def test_defaults():
    with mock.patch.dict(os.environ, {}, clear=True):
        cfg = Config.from_env()
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 9090
    assert cfg.default_namespace == "/sessions"


def test_overrides():
    env = {
        "ANXB_HOST": "0.0.0.0",
        "ANXB_PORT": "8765",
        "ANXB_ANUNIX": "false",
        "ANXB_HEADLESS": "false",
    }
    with mock.patch.dict(os.environ, env, clear=True):
        cfg = Config.from_env()
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 8765
    assert cfg.anunix_enabled is False
    assert cfg.headless_default is False
