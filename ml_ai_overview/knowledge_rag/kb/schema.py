from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScamCard:
    id: str
    scam_type: str
    channel: str
    languages: list
    title: str
    example_messages: list
    call_script: str
    red_flags: list
    what_to_do: str
    source: dict
    if_already_opened: str = ""
    post_open_keywords: list = field(default_factory=list)
    severity: str = ""

    def validate(self) -> None:
        required_non_empty = {
            "id": self.id,
            "scam_type": self.scam_type,
            "title": self.title,
            "what_to_do": self.what_to_do,
        }
        for field_name, value in required_non_empty.items():
            if not value or not str(value).strip():
                raise ValueError(f"ScamCard field '{field_name}' is missing or empty")

        for list_field, value in [
            ("example_messages", self.example_messages),
            ("red_flags", self.red_flags),
        ]:
            if not value:
                raise ValueError(f"ScamCard field '{list_field}' is missing or empty")

        if not self.source:
            raise ValueError("ScamCard field 'source' is missing or empty")
        for key in ("name", "url", "date"):
            if key not in self.source or not self.source[key]:
                raise ValueError(f"ScamCard source is missing required key '{key}'")
