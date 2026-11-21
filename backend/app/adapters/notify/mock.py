"""In-memory notification recorder for tests and local development."""

from dataclasses import dataclass
from typing import ClassVar


@dataclass
class MockNotification:
    chat_id: str
    text: str


class MockNotifier:
    notifications: ClassVar[list[MockNotification]] = []

    @classmethod
    def reset(cls) -> None:
        cls.notifications.clear()

    async def notify(self, *, chat_id: str, text: str) -> bool:
        MockNotifier.notifications.append(MockNotification(chat_id=chat_id, text=text))
        return True
