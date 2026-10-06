import pytest

from app.guardrails.tool_permissions import PermissionDenied, check_external_write
from app.settings import settings

PROD_MIGRATION = """python3 -c "
import pymongo
client = pymongo.MongoClient('mongodb://192.168.100.10:27018/?directConnection=true')
client['jobseeker_t_x'].job_alerts.replace_one({'_id': 1}, {}, upsert=True)
client['jobseeker_t_y'].job_alerts.delete_one({'_id': 1})"
"""


def test_prod_write_needs_approval():
    with pytest.raises(PermissionDenied, match="NEEDS_HUMAN"):
        check_external_write(PROD_MIGRATION, settings.workspace_root, approved=False)
    check_external_write(PROD_MIGRATION, settings.workspace_root, approved=True)   # after the human said yes


def test_reads_and_local_work_are_fine():
    check_external_write("""python3 -c "import pymongo; print(pymongo.MongoClient('mongodb://192.168.100.10:27018').list_database_names())" """,
                         settings.workspace_root, approved=False)
    check_external_write("rm -rf build && pytest -q", settings.workspace_root, approved=False)
    for cmd in ("psql -h db.local.internal -c 'UPDATE users SET a=1'", "ssh docker-vm docker service rm x",
                "curl -X DELETE http://192.168.100.10:8080/api/items/1"):
        with pytest.raises(PermissionDenied):
            check_external_write(cmd, settings.workspace_root, approved=False)


def test_scripts_run_by_the_command_are_inspected(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "workspace_root", tmp_path)
    (tmp_path / "fix.py").write_text("import pymongo\nc = pymongo.MongoClient('mongodb://192.168.100.10:27018')\nc.db.x.update_many({}, {'$set': {'a': 1}})\n")
    with pytest.raises(PermissionDenied):
        check_external_write("python3 fix.py", tmp_path, approved=False)
