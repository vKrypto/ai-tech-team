from app.agents.base import parse_needs_human


def test_no_protocol_line():
    assert parse_needs_human("all good") == ("all good", None)


def test_extracts_last_line_json():
    text = 'Some work.\nNEEDS_HUMAN: {"problem": "Which DB?", "options": [{"id": "A", "label": "Postgres"}, "B"]}'
    body, h = parse_needs_human(text)
    assert body == "Some work."
    assert h["problem"] == "Which DB?"
    assert h["options"][0]["id"] == "A" and h["options"][1] == {"id": "B", "label": "B"}


def test_broken_json_still_asks():
    _, h = parse_needs_human("NEEDS_HUMAN: {not json}")
    assert h["problem"] == "{not json}" and h["options"] == []
