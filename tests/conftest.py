"""Offline test defaults must override a developer's live sponsor configuration.

Individual provider-contract tests can explicitly replace these values and use a
mock transport. Merely having a private .env must never turn pytest into a live
model call or start a messaging worker.
"""

import pytest


@pytest.fixture(autouse=True)
def offline_sponsor_defaults(monkeypatch):
    for key, value in {
        "CHALK_ENABLED": "false", "CHALK_ROUTER_API_KEY": "", "CHALK_ENV_ID": "",
        "CHALK_MODEL": "", "PHOTON_ENABLED": "false", "PHOTON_API_KEY": "",
        "PHOTON_PROJECT_ID": "", "PHOTON_ROUTES_JSON": "[]",
        "GROK_VOICE_ENABLED": "false", "XAI_API_KEY": "",
    }.items():
        monkeypatch.setenv(key, value)
