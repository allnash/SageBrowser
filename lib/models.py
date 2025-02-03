from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
import uuid


class Role(str, Enum):
    WEB_BROWSER = "web_browser"
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    content: str
    role: Role
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
            "message_id": self.message_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        return cls(
            content=data["content"],
            role=Role(data["role"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            metadata=data.get("metadata", {}),
            message_id=data.get("message_id", str(uuid.uuid4()))
        )


@dataclass
class Conversation:
    messages: List[Message] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    title: Optional[str] = None

    def add_message(self, content: str, role: Role) -> Message:
        message = Message(content=content, role=role)
        self.messages.append(message)
        self.updated_at = datetime.now()
        return message

    def get_messages(self, limit: Optional[int] = None) -> List[Message]:
        if limit is None:
            return self.messages
        return self.messages[-limit:]

    def get_last_message(self) -> Optional[Message]:
        return self.messages[-1] if self.messages else None


@dataclass
class DataSource:
    name: str  # Required field comes first
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: Optional[str] = None
    connection_data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "connection_data": self.connection_data,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DataSource':
        return cls(
            name=data["name"],
            id=data.get("id", str(uuid.uuid4())),
            description=data.get("description"),
            connection_data=data.get("connection_data", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=data.get("metadata", {})
        )