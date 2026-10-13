"""Shared data structure for posts collected from any source."""

from dataclasses import dataclass, field


@dataclass
class Post:
    source: str
    post_id: str
    url: str
    text: str
    created_at: str = ""
    metadata: dict = field(default_factory=dict)