import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from emporio_agent.complaints import Complaints

CG = ZoneInfo("America/Campo_Grande")
NOW = datetime(2026, 11, 3, 15, 30, tzinfo=CG)


def lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def complaints(tmp_path):
    return Complaints(tmp_path / "complaints.jsonl", now=lambda: NOW)


def test_a_complaint_is_saved_with_description_contact_and_time(complaints, tmp_path):
    result = complaints.register_complaint(
        description="O violão chegou com um risco no tampo.", contact="(67) 99789-0123"
    )

    assert result.protocol == "00001"
    assert lines(tmp_path / "complaints.jsonl") == [
        {
            "protocol": "00001",
            "kind": "complaint",
            "description": "O violão chegou com um risco no tampo.",
            "contact": "(67) 99789-0123",
            "created_at": "2026-11-03T15:30:00-04:00",
        }
    ]


def test_records_are_appended_with_increasing_protocols(complaints, tmp_path):
    first = complaints.register_complaint("Demora na entrega.", "ana@jmail.com")
    second = complaints.register_complaint("Atendimento ruim.", "(67) 98432-1098")

    assert (first.protocol, second.protocol) == ("00001", "00002")
    assert [r["description"] for r in lines(tmp_path / "complaints.jsonl")] == [
        "Demora na entrega.",
        "Atendimento ruim.",
    ]


def test_numbering_continues_after_a_restart(tmp_path):
    path = tmp_path / "complaints.jsonl"
    Complaints(path, now=lambda: NOW).register_complaint("Primeira.", "a@b.com")

    result = Complaints(path, now=lambda: NOW).register_complaint("Segunda.", "a@b.com")

    assert result.protocol == "00002"


def test_the_folder_is_created_when_missing(tmp_path):
    path = tmp_path / "var" / "data" / "complaints.jsonl"

    Complaints(path, now=lambda: NOW).register_complaint("Teste.", "a@b.com")

    assert path.exists()


def test_a_handoff_is_saved_in_the_same_file_with_its_own_kind(complaints, tmp_path):
    complaints.register_complaint("Demora na entrega.", "ana@jmail.com")

    result = complaints.request_handoff("Cliente quer cancelar o pedido 13.", "(67) 99456-7890")

    assert result.protocol == "00002"
    assert lines(tmp_path / "complaints.jsonl")[1]["kind"] == "handoff"
    assert lines(tmp_path / "complaints.jsonl")[1]["description"] == "Cliente quer cancelar o pedido 13."


@pytest.mark.parametrize("description, contact", [("", "a@b.com"), ("  ", "a@b.com"), ("Problema.", ""), ("Problema.", "   ")])
def test_nothing_is_saved_without_a_description_and_a_contact(complaints, tmp_path, description, contact):
    with pytest.raises(ValueError):
        complaints.register_complaint(description, contact)
    with pytest.raises(ValueError):
        complaints.request_handoff(description, contact)

    assert not (tmp_path / "complaints.jsonl").exists()


def test_a_write_failure_is_raised_not_swallowed(tmp_path):
    broken = Complaints(tmp_path, now=lambda: NOW)  # the path is a directory, so it cannot be written

    with pytest.raises(OSError):
        broken.register_complaint("Problema.", "a@b.com")
