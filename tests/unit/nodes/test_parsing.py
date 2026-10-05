from app.workflows.coding.nodes.review import verdict
from app.workflows.task_execution.policies import parse_steps, validation_passed


def test_parse_steps_takes_last_json_block_and_caps():
    text = 'x\n```json\n[{"agent":"senior_engineer","instruction":"a"}]\n```\nrevised:\n```json\n' \
           '[{"agent":"researcher","instruction":"b"},{"agent":"bogus","instruction":"c"},{"agent":"senior_engineer","instruction":"d"}]\n```'
    steps = parse_steps(text, 2)
    assert [s["instruction"] for s in steps] == ["b", "c"] and steps[1]["agent"] == "architect"


def test_parse_steps_fallback():
    assert parse_steps("no plan here", 5)[0]["agent"] == "architect"


def test_verdicts():
    assert verdict("...\nVERDICT: APPROVED") and not verdict("VERDICT: CHANGES_REQUESTED")
    assert not verdict("VERDICT: APPROVED\nlater: VERDICT: CHANGES_REQUESTED")
    assert validation_passed("VALIDATION: PASS") and not validation_passed("VALIDATION: FAIL")
    assert validation_passed("no verdict line")
