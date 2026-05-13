"""Google Drive and Slides API access via a CultureBotAI service account.

The canonical service account is:
    culturebot-data-downloader@culturebot-476200.iam.gserviceaccount.com

Its JSON key is located by, in order of precedence:
  1. `credentials_path` argument
  2. `$GOOGLE_APPLICATION_CREDENTIALS` env var (the Google-standard variable)
  3. `$CULTUREBOT_GOOGLE_CREDENTIALS` env var (project-specific override)
  4. `~/.config/culturebot/credentials.json`
  5. `<repo-research-writer>/credentials.json` (legacy: the rrwrite checkout
     historically holds the only copy on this machine)

Install with: `pip install wizard-core[google]`.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional, Sequence

DEFAULT_SCOPES = (
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/presentations.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
)

EXPECTED_CLIENT_EMAIL = (
    "culturebot-data-downloader@culturebot-476200.iam.gserviceaccount.com"
)

_LEGACY_RRWRITE_CREDS = (
    Path.home()
    / "Documents/VIMSS/ontology/repo-research-writer/credentials.json"
)


class GoogleCredentialsNotFoundError(FileNotFoundError):
    """Raised when no service-account key file can be located."""


def locate_credentials(credentials_path: Optional[Path] = None) -> Path:
    """Return the first existing path for the service-account JSON."""
    candidates: List[Path] = []
    if credentials_path:
        candidates.append(Path(credentials_path).expanduser())
    for env_var in ("GOOGLE_APPLICATION_CREDENTIALS", "CULTUREBOT_GOOGLE_CREDENTIALS"):
        value = os.environ.get(env_var)
        if value:
            candidates.append(Path(value).expanduser())
    candidates.append(Path.home() / ".config/culturebot/credentials.json")
    candidates.append(_LEGACY_RRWRITE_CREDS)

    for path in candidates:
        if path.exists():
            return path

    raise GoogleCredentialsNotFoundError(
        "No CultureBotAI service-account JSON found. Looked at:\n  - "
        + "\n  - ".join(str(p) for p in candidates)
        + "\n\nSet GOOGLE_APPLICATION_CREDENTIALS to the file path, or place it "
          "at ~/.config/culturebot/credentials.json."
    )


class GoogleClient:
    """Builds Drive / Slides / Docs services from a CultureBotAI service-account key."""

    def __init__(
        self,
        credentials_path: Optional[Path] = None,
        scopes: Sequence[str] = DEFAULT_SCOPES,
    ):
        try:
            from google.oauth2 import service_account  # noqa: F401
            from googleapiclient.discovery import build  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "google-auth and google-api-python-client are required. "
                "Install with: pip install wizard-core[google]"
            ) from e

        self.credentials_path = locate_credentials(credentials_path)
        self.scopes = tuple(scopes)
        self.logger = logging.getLogger(__name__)

        from google.oauth2 import service_account

        self._credentials = service_account.Credentials.from_service_account_file(
            str(self.credentials_path), scopes=list(self.scopes)
        )
        self._drive = None
        self._slides = None
        self._docs = None

    @property
    def client_email(self) -> str:
        return getattr(self._credentials, "service_account_email", "(unknown)")

    @property
    def drive(self):
        if self._drive is None:
            from googleapiclient.discovery import build

            self._drive = build("drive", "v3", credentials=self._credentials, cache_discovery=False)
        return self._drive

    @property
    def slides(self):
        if self._slides is None:
            from googleapiclient.discovery import build

            self._slides = build("slides", "v1", credentials=self._credentials, cache_discovery=False)
        return self._slides

    @property
    def docs(self):
        if self._docs is None:
            from googleapiclient.discovery import build

            self._docs = build("docs", "v1", credentials=self._credentials, cache_discovery=False)
        return self._docs

    def whoami(self) -> dict:
        """Smoke-test access by issuing a tiny Drive request.

        Returns a dict with the service-account email, key file path,
        and the count of accessible items in the test query.
        """
        try:
            result = (
                self.drive.files()
                .list(
                    pageSize=1,
                    fields="files(id,name)",
                    q="trashed=false",
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            sample = result.get("files", [])
            return {
                "ok": True,
                "client_email": self.client_email,
                "credentials_path": str(self.credentials_path),
                "sample_file": sample[0] if sample else None,
            }
        except Exception as e:
            return {
                "ok": False,
                "client_email": self.client_email,
                "credentials_path": str(self.credentials_path),
                "error": f"{type(e).__name__}: {e}",
            }
