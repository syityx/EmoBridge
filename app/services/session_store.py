from __future__ import annotations

import re
from pathlib import Path

from schemas.chat import SessionMessage


SESSION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


class SessionStore:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def validate_session_id(self, session_id: str) -> None:
        if not SESSION_ID_PATTERN.fullmatch(session_id):
            raise ValueError("session_id 仅允许字母、数字、下划线和中划线")

    def _session_file(self, session_id: str) -> Path:
        return self.root_dir / f"{session_id}.txt"

    def read_messages(self, session_id: str) -> list[SessionMessage]:
        path = self._session_file(session_id)
        if not path.exists():
            return []

        messages: list[SessionMessage] = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith("user:"):
                messages.append(SessionMessage(role="user", content=line[5:].strip()))
            elif line.startswith("assistant:"):
                messages.append(SessionMessage(role="assistant", content=line[10:].strip()))
        return messages

    def append_message(self, session_id: str, role: str, content: str) -> None:
        safe_content = content.replace("\n", " ").strip()
        if not safe_content:
            return
        path = self._session_file(session_id)
        with path.open("a", encoding="utf-8") as file:
            file.write(f"{role}: {safe_content}\n")
