"""Тесты структуры YAML-контента (без подключения к БД)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_CONTENT = Path(__file__).resolve().parents[1] / "content"


def _load(name: str) -> dict:
    with (_CONTENT / name).open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_round1_shape():
    data = _load("round1.yaml")
    assert data["round_code"] == "R1"
    qs = data["questions"]
    assert len(qs) == 5
    for q in qs:
        p = q["payload"]
        assert isinstance(p["text"], str)
        assert len(p["options"]) == 4
        assert 0 <= p["correct_index"] <= 3
        assert q["points"] == 100


def test_round2_shape():
    data = _load("round2.yaml")
    assert data["round_code"] == "R2"
    topics = data["topics"]
    assert len(topics) == 3
    total = 0
    seen_codes: set[str] = set()
    for t in topics:
        assert "topic_code" in t
        for q in t["questions"]:
            total += 1
            seen_codes.add(q["code"])
            p = q["payload"]
            assert len(p["options"]) == 3
            assert 0 <= p["correct_index"] <= 2
            assert q["points"] in {100, 200, 300, 400}
    assert total == 6
    assert len(seen_codes) == 6


def test_round3_shape():
    data = _load("round3.yaml")
    assert data["round_code"] == "R3"
    qs = data["questions"]
    assert len(qs) == 3
    for q in qs:
        p = q["payload"]
        assert len(p["options"]) == 2
        assert 0 <= p["correct_index"] <= 1
        assert "image_path" in p
        assert p["image_path"].startswith("assets/round3/")


def test_broadcasts_yaml_deprecated_empty_templates():
    data = _load("broadcasts.yaml")
    assert data["templates"] == []


@pytest.mark.parametrize(
    "filename,expected_codes",
    [
        ("round1.yaml", {"R1"}),
        ("round2.yaml", {"R2"}),
        ("round3.yaml", {"R3"}),
    ],
)
def test_round_codes_match_file(filename, expected_codes):
    data = _load(filename)
    assert {data["round_code"]} == expected_codes
