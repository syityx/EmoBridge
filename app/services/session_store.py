from __future__ import annotations

import re


SESSION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def validate_session_id(session_id: str) -> None:
    if not SESSION_ID_PATTERN.fullmatch(session_id):
        raise ValueError("session_id 仅允许字母、数字、下划线和中划线")
