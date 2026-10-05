from app.agents.registry import ROLES, roster
from app.tools import registry


def test_catalog_lists_real_tools_per_group():
    cat = registry.catalog()
    assert set(cat) == set(registry.GROUPS) == set(registry.GROUP_INFO)   # every group documented
    names = {t["name"] for tools in cat.values() for t in tools}
    assert {"read_file", "edit_file", "run_command", "git_commit", "gh", "web_search", "browser", "load_skill"} <= names
    assert all(t["description"] for tools in cat.values() for t in tools)


def test_every_agent_documents_its_responsibilities():
    by_role = {r["role"]: r for r in roster()}
    for role in ("orchestrator", *ROLES):
        assert by_role[role].get("title") and by_role[role].get("responsibilities"), role
