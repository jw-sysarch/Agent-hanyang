from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class PageSummary:
    url: str
    title: str
    headings: list[str]
    links: list[dict[str, str]]
    text_preview: str
    cookies: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BoardSummary:
    id: str
    name: str
    href: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ArticleSummary:
    title: str
    href: str
    author: str
    created_at: str
    preview: str
    comment_count: str
    like_count: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
