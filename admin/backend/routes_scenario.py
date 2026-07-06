import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from config import SCENARIO_PATH, SCENARIO_BACKUP_DIR

router = APIRouter(prefix="/api/scenario", tags=["scenario"])


@router.get("")
async def get_scenario():
    return json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))


@router.put("")
async def put_scenario(scenario: dict):
    if "start" not in scenario or "blocks" not in scenario:
        raise HTTPException(status_code=422, detail="Scenario must contain 'start' and 'blocks'")
    if scenario["start"] not in scenario["blocks"]:
        raise HTTPException(status_code=422, detail="'start' must reference an existing block")

    SCENARIO_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    backup_path = SCENARIO_BACKUP_DIR / f"scenario_{timestamp}.json"
    backup_path.write_text(SCENARIO_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    SCENARIO_PATH.write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "backup": backup_path.name}
