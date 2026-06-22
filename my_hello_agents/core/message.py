"""Message system."""

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel


MessageRole = Literal["user", "assistant", "system", "tool", "summary"]


class Message(BaseModel):
    """A single conversation message."""

    content: str
    role: MessageRole
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

    def __init__(self, content: str, role: MessageRole, **kwargs: Any):
        super().__init__(
            content=content,
            role=role,
            timestamp=kwargs.get("timestamp", datetime.now()),
            metadata=kwargs.get("metadata"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert the message to a dictionary."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create a message from a dictionary."""
        timestamp = data.get("timestamp")
        if timestamp and isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        return cls(
            content=data["content"],
            role=data["role"],
            timestamp=timestamp,
            metadata=data.get("metadata"),
        )

    def to_text(self) -> str:
        """Format the message as text for prompt context."""
        return f"[{self.role}] {self.content}"

    def __str__(self) -> str:
        return self.to_text()
