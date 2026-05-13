"""Smoke tests for GoogleClient credentials discovery and (optional) live access.

The live-access test runs only if a credentials file is actually findable on
the machine; otherwise it skips. Pure offline tests exercise the lookup logic.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

google_client_mod = pytest.importorskip("wizard_core.google_client")
GoogleClient = google_client_mod.GoogleClient
GoogleCredentialsNotFoundError = google_client_mod.GoogleCredentialsNotFoundError
EXPECTED_CLIENT_EMAIL = google_client_mod.EXPECTED_CLIENT_EMAIL
locate_credentials = google_client_mod.locate_credentials


def _credentials_findable() -> bool:
    try:
        locate_credentials()
        return True
    except GoogleCredentialsNotFoundError:
        return False


def test_locate_credentials_explicit_path(tmp_path: Path) -> None:
    fake = tmp_path / "creds.json"
    fake.write_text("{}")
    assert locate_credentials(fake) == fake


def test_locate_credentials_raises_when_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.delenv("CULTUREBOT_GOOGLE_CREDENTIALS", raising=False)
    # Point HOME at a tmp dir with no .config/culturebot/credentials.json and
    # patch out the legacy rrwrite path so all candidates miss.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        google_client_mod,
        "_LEGACY_RRWRITE_CREDS",
        tmp_path / "no_legacy.json",
    )
    with pytest.raises(GoogleCredentialsNotFoundError):
        locate_credentials(tmp_path / "definitely-does-not-exist.json")


@pytest.mark.skipif(
    not _credentials_findable(),
    reason="No CultureBotAI service-account credentials on this machine",
)
def test_live_whoami_against_real_credentials() -> None:
    client = GoogleClient()
    creds_data = json.loads(Path(client.credentials_path).read_text())
    assert creds_data.get("client_email") == EXPECTED_CLIENT_EMAIL
    result = client.whoami()
    assert result["ok"], f"whoami failed: {result}"
    assert result["client_email"] == EXPECTED_CLIENT_EMAIL
