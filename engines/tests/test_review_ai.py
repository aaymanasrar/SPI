"""The AI spec reader's guard: what a model says is kept only if the clause says it.

A fake model stands in for Ollama, so these run without one and can be made to
lie on purpose.
"""
from __future__ import annotations

import json

import pytest

from craft.review import ai
from craft.review.spec import _clauses


def clauses(*lines):
    return _clauses([("p.1", ln) for ln in lines])


@pytest.fixture
def model(monkeypatch):
    """Configure a model and make it answer with whatever the test sets."""
    monkeypatch.setenv("SPI_AI_PROVIDER", "ollama")
    monkeypatch.setenv("SPI_AI_MODEL", "fake:1b")
    answer = {"requirements": []}
    sent = []

    def fake(cfg, system, user, timeout):
        sent.append((system, user))
        return json.dumps(answer)
    monkeypatch.setattr(ai, "_call", fake)
    return answer, sent


def test_off_by_default(monkeypatch):
    monkeypatch.delenv("SPI_AI_PROVIDER", raising=False)
    out = ai.read_clauses(clauses("1.1 Provide 4 IP cameras."))
    assert out["run"] is None and out["requirements"] == []


def test_a_faithful_reading_is_kept_and_marked(model):
    answer, sent = model
    answer["requirements"] = [{"clause_id": "c1", "kind": "quantity", "device_type": "camera",
                               "value": 4, "quote": "Provide 4 IP cameras"}]
    out = ai.read_clauses(clauses("1.1 Provide 4 IP cameras.", "1.2 The site is in Riyadh."))
    [r] = out["requirements"]
    assert (r["kind"], r["device_type"], r["value"], r["system"]) == ("quantity", "camera", 4, "cctv")
    assert r["clause"] == "1.1" and r["read_by"] == "ai:fake:1b"
    # Only the clause that requires something is sent; the skill is the system prompt.
    assert "Riyadh" not in sent[0][1] and "SPI spec reader skill" in sent[0][0]
    assert out["run"]["skill_version"] and out["run"]["accepted"] == 1


@pytest.mark.parametrize("bad,why", [
    ({"clause_id": "c9", "kind": "system", "system": "cctv", "quote": "Provide"}, "not sent"),
    ({"clause_id": "c1", "kind": "quantity", "device_type": "camera", "value": 6,
      "quote": "Provide 6 IP cameras"}, "quote is not in the clause"),
    ({"clause_id": "c1", "kind": "quantity", "device_type": "camera", "value": 6,
      "quote": "Provide 4 IP cameras"}, "number is not in its quote"),
    ({"clause_id": "c1", "kind": "quantity", "device_type": None, "value": 4,
      "quote": "Provide 4 IP cameras"}, "no device"),
])
def test_an_invented_reading_is_refused_with_the_reason(model, bad, why):
    answer, _ = model
    answer["requirements"] = [bad]
    out = ai.read_clauses(clauses("1.1 Provide 4 IP cameras."))
    assert out["requirements"] == []
    assert why in out["rejected"][0]["why"]


def test_number_words_count_as_the_number(model):
    answer, _ = model
    answer["requirements"] = [{"clause_id": "c1", "kind": "rate", "device_type": "data_outlet",
                               "value": 2, "per": "workstation",
                               "quote": "Two data outlets shall be provided per workstation"}]
    out = ai.read_clauses(clauses("4.1 Two data outlets shall be provided per workstation."))
    assert out["requirements"][0]["value"] == 2


def test_a_model_that_does_not_answer_is_reported_not_fatal(monkeypatch):
    monkeypatch.setenv("SPI_AI_PROVIDER", "ollama")
    monkeypatch.setenv("SPI_AI_URL", "http://127.0.0.1:9")   # nothing listens here
    out = ai.read_clauses(clauses("1.1 Provide 4 IP cameras."), timeout=2)
    assert out["requirements"] == [] and out["run"]["errors"]


def test_merge_marks_agreement_and_keeps_the_exception():
    p = {"clause": "5.4", "location": "p.1", "text": "…", "kind": "coverage", "system": "fire_alarm",
         "device_type": "smoke_detector", "rooms": ["all"]}
    a = {**p, "read_by": "ai:m", "except_rooms": ["toilet", "stair"]}
    [m] = ai.merge([p], [a])
    assert m["read_by"] == "both" and m["except_rooms"] == ["toilet", "stair"]


def test_merge_keeps_both_when_they_disagree():
    p = {"clause": "2.1", "location": "p.1", "text": "…", "kind": "quantity", "system": "cctv",
         "device_type": "camera", "value": 4}
    a = {**p, "value": 6, "read_by": "ai:m"}
    out = ai.merge([p], [a])
    assert sorted(r["read_by"] for r in out) == ["ai:m", "rules"]


def test_attribute_values_must_be_that_attribute_and_in_the_quote(model):
    answer, _ = model
    q = "The fire alarm system shall be analogue addressable to NFPA 72, Siemens or approved equal"
    answer["requirements"] = [
        # A mixed bag under one attribute: only the technology survives, normalised.
        {"clause_id": "c1", "kind": "attribute", "device_type": "fire_alarm_panel", "attribute": "technology",
         "values": ["analogue addressable", "NFPA 72", "Siemens", "approved equal"], "quote": q},
        # A value the clause never states.
        {"clause_id": "c1", "kind": "attribute", "system": "fire_alarm", "attribute": "technology",
         "values": ["conventional"], "quote": q},
    ]
    out = ai.read_clauses(clauses("1.1 " + q + "."))
    [kept] = out["requirements"]
    assert kept["values"] == ["addressable"]
    # The clause names the system, not a panel.
    assert kept["device_type"] is None and kept["system"] == "fire_alarm"
    assert "none of its values" in out["rejected"][0]["why"]


def test_a_count_for_a_device_the_quote_does_not_name_is_refused(model):
    answer, _ = model
    answer["requirements"] = [{"clause_id": "c1", "kind": "quantity", "device_type": "card_reader",
                               "value": 4, "quote": "Provide 4 IP cameras"}]
    out = ai.read_clauses(clauses("1.1 Provide 4 IP cameras."))
    assert out["rejected"][0]["why"] == "its device is not named in its quote"


def test_merge_matches_when_the_rule_reader_left_the_system_blank():
    p = {"clause": "3.2", "location": "p.1", "text": "…", "kind": "attribute", "system": None,
         "device_type": None, "attribute": "cable_category", "values": ["Cat6A"]}
    a = {**p, "system": "data", "read_by": "ai:m"}
    [m] = ai.merge([p], [a])
    assert m["read_by"] == "both" and m["system"] == "data"
