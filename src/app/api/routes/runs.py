from fastapi import APIRouter, HTTPException

from ...persistence import artifacts
from ...services.scheduler import dashboard
from ...services.scheduler.dashboard import Conflict
from ...workflows import registry
from ..dependencies import run_or_404

router = APIRouter(prefix="/api", tags=["runs"])


@router.get("/runs/{run_id}")
def get(run_id: str):
    return run_or_404(run_id)


@router.get("/runs/{run_id}/nodes/{node}")
def node_outputs(run_id: str, node: str):
    run = run_or_404(run_id)
    return {"node": node, "state": (run.get("nodes") or {}).get(node), "outputs": artifacts.for_node(run_id, node)}


@router.post("/runs/{run_id}/nodes/{node}/rerun")
def rerun(run_id: str, node: str):
    run_or_404(run_id)
    try:
        return dashboard.rerun(run_id, node)
    except Conflict as e:
        raise HTTPException(409, str(e))


@router.get("/workflows")
def workflows():
    return [registry.describe(n) for n in registry.names()]
