import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from config import (
    SCENARIO_PATH,
    SCENARIO_BACKUP_DIR,
    FILES_DIR,
    SAVE_AS_FIELDS,
    VALIDATOR_NAMES,
    BLOCK_TYPES,
    BLOCK_REQUIRED_FIELDS,
)

router = APIRouter(prefix="/api/scenario", tags=["scenario"])


@router.get("")
async def get_scenario():
    return json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))


@router.get("/meta")
async def get_scenario_meta():
    scenario = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
    files = sorted(p.name for p in FILES_DIR.iterdir() if p.is_file()) if FILES_DIR.exists() else []
    return {
        "block_ids": sorted(scenario["blocks"].keys()),
        "start": scenario["start"],
        "block_types": BLOCK_TYPES,
        "save_as_fields": SAVE_AS_FIELDS,
        "validators": VALIDATOR_NAMES,
        "files": files,
    }


def _validate_scenario(scenario: dict) -> None:
    if "start" not in scenario or "blocks" not in scenario:
        raise HTTPException(status_code=422, detail="Сценарий должен содержать 'start' и 'blocks'")

    blocks = scenario["blocks"]
    if scenario["start"] not in blocks:
        raise HTTPException(status_code=422, detail="'start' должен указывать на существующий блок")

    for block_id, block in blocks.items():
        block_type = block.get("type")
        if block_type not in BLOCK_REQUIRED_FIELDS:
            raise HTTPException(status_code=422, detail=f"Блок '{block_id}': неизвестный тип '{block_type}'")

        for field in BLOCK_REQUIRED_FIELDS[block_type]:
            if not block.get(field):
                raise HTTPException(
                    status_code=422, detail=f"Блок '{block_id}': не заполнено обязательное поле '{field}'"
                )

        if block_type == "input" and block["save_as"] not in SAVE_AS_FIELDS:
            raise HTTPException(
                status_code=422, detail=f"Блок '{block_id}': недопустимое значение save_as '{block['save_as']}'"
            )
        if block_type == "input" and block.get("validate") and block["validate"] not in VALIDATOR_NAMES:
            raise HTTPException(
                status_code=422, detail=f"Блок '{block_id}': недопустимое значение validate '{block['validate']}'"
            )

        if block_type == "document":
            file_names = block["file"] if isinstance(block["file"], list) else [block["file"]]
            for name in file_names:
                if not (FILES_DIR / name).exists():
                    raise HTTPException(status_code=422, detail=f"Блок '{block_id}': файл '{name}' не найден")

        ref_fields = [f for f in ("next", "auto_next", "yes", "no") if block.get(f)]
        for field in ref_fields:
            if block[field] not in blocks:
                raise HTTPException(
                    status_code=422,
                    detail=f"Блок '{block_id}': поле '{field}' ссылается на несуществующий блок '{block[field]}'",
                )

        for button in block.get("buttons", []):
            if not button.get("text") or not button.get("next"):
                raise HTTPException(status_code=422, detail=f"Блок '{block_id}': у кнопки должны быть text и next")
            if button["next"] not in blocks:
                raise HTTPException(
                    status_code=422,
                    detail=f"Блок '{block_id}': кнопка ссылается на несуществующий блок '{button['next']}'",
                )


@router.put("")
async def put_scenario(scenario: dict):
    _validate_scenario(scenario)

    SCENARIO_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    backup_path = SCENARIO_BACKUP_DIR / f"scenario_{timestamp}.json"
    backup_path.write_text(SCENARIO_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    SCENARIO_PATH.write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "backup": backup_path.name}
