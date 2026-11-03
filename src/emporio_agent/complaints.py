import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Registration:
    protocol: str


class Complaints:
    """Local JSON Lines log of complaints and human-handoff requests (description + contact only)."""

    def __init__(self, path: Path, now):
        self._path = Path(path)
        self._now = now

    def register_complaint(self, description: str, contact: str) -> Registration:
        return self._save("complaint", description, contact)

    def request_handoff(self, reason: str, contact: str) -> Registration:
        return self._save("handoff", reason, contact)

    def _save(self, kind: str, description: str, contact: str) -> Registration:
        if not description.strip() or not contact.strip():
            raise ValueError("description and contact are required")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "protocol": self._next_protocol(),
            "kind": kind,
            "description": description.strip(),
            "contact": contact.strip(),
            "created_at": self._now().isoformat(),
        }
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return Registration(record["protocol"])

    def _next_protocol(self) -> str:
        count = 0
        if self._path.exists():
            with open(self._path, encoding="utf-8") as f:
                count = sum(1 for line in f if line.strip())
        return f"{count + 1:05d}"
