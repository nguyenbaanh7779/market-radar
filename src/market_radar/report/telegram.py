"""Send the newsletter through a Telegram bot."""

from __future__ import annotations

import requests

API_URL = "https://api.telegram.org/bot{token}/sendMessage"
MAX_CHARS = 4000  # Telegram allows 4096 per message


def split_message(text: str, limit: int = MAX_CHARS) -> list[str]:
    """Split text on line breaks into chunks Telegram accepts.

    Args:
        text: Full message.
        limit: Maximum characters per chunk.

    Returns:
        Chunks in order; a single over-long line is cut hard.
    """
    chunks, current = [], ""
    for line in text.splitlines(keepends=True):
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if len(current) + len(line) > limit:
            chunks.append(current)
            current = ""
        current += line
    if current.strip():
        chunks.append(current)
    return chunks


def send_telegram(
    text: str,
    token: str,
    chat_id: str,
    session: requests.Session | None = None,
) -> int:
    """Send a plain-text message, split if needed.

    Args:
        text: Message text.
        token: Bot token from @BotFather.
        chat_id: Chat to post to.
        session: HTTP session (injected in tests).

    Returns:
        Number of messages sent.

    Raises:
        requests.HTTPError: If Telegram rejects a message.
    """
    http = session or requests.Session()
    chunks = split_message(text)
    for chunk in chunks:
        response = http.post(
            API_URL.format(token=token),
            data={"chat_id": chat_id, "text": chunk,
                  "disable_web_page_preview": "true"},
            timeout=30,
        )
        response.raise_for_status()
    return len(chunks)
