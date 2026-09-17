import json

from fastapi import APIRouter, HTTPException

from config import (
    CONSULTATION_DONE_BLOCK,
    CONSULTATION_START_BLOCK,
    DEFAULT_SCENARIO_PLATFORM,
    SCENARIO_PLATFORMS,
    TAG_CONSULTATION_DONE,
    TAG_CONSULTATION_STARTED,
)

router = APIRouter(prefix="/api/scenario-graph", tags=["scenario-graph"])

TYPE_LABELS = {
    "message": "Сообщение",
    "document": "Документ",
    "input": "Запрос данных",
    "condition": "Проверка подписки",
    "delay": "Пауза",
}

AUTO_TAGS = {
    CONSULTATION_START_BLOCK: TAG_CONSULTATION_STARTED,
    CONSULTATION_DONE_BLOCK: TAG_CONSULTATION_DONE,
}


def _resolve_platform(platform: str) -> dict:
    config = SCENARIO_PLATFORMS.get(platform)
    if config is None:
        raise HTTPException(status_code=422, detail=f"Неизвестная платформа сценария: {platform}")
    return config


def _clean_text(text: str | None) -> str | None:
    if not text:
        return None
    return text.strip()


@router.get("")
async def get_scenario_graph(platform: str = DEFAULT_SCENARIO_PLATFORM):
    path = _resolve_platform(platform)["path"]
    scenario = json.loads(path.read_text(encoding="utf-8"))
    blocks = scenario["blocks"]
    start_id = scenario["start"]

    def button_next(button: dict) -> str | None:
        if "next" in button:
            return button["next"]
        if button.get("consent"):
            # У кнопки согласия (CONSENT_BLOCK) нет фиксированного "next" в JSON —
            # следующий блок решает код бота (PENDING_DEEPLINK либо общее меню).
            # Для графа считаем целью то же, куда ведёт condition-блок при "подписан".
            start_block = blocks.get(start_id, {})
            return start_block.get("yes")
        return None

    nodes = []
    edges = []

    for block_id, block in blocks.items():
        block_type = block.get("type", "message")
        nodes.append(
            {
                "id": block_id,
                "label": block.get("name") or block_id,
                "type": block_type,
                "type_label": TYPE_LABELS.get(block_type, block_type),
                "is_start": block_id == start_id,
                "preview": _clean_text(block.get("text")),
                "auto_tag": AUTO_TAGS.get(block_id),
                "buttons": [{"text": b["text"], "next": button_next(b)} for b in block.get("buttons", [])],
            }
        )

        if block_type == "condition":
            edges.append({"from": block_id, "to": block["yes"], "label": "подписан"})
            edges.append({"from": block_id, "to": block["no"], "label": "не подписан"})
        else:
            if block.get("next"):
                edges.append({"from": block_id, "to": block["next"], "label": None})
            if block.get("auto_next"):
                edges.append({"from": block_id, "to": block["auto_next"], "label": "автоматически"})
            for button in block.get("buttons", []):
                target = button_next(button)
                if target:
                    edges.append({"from": block_id, "to": target, "label": button["text"]})

    return {"start": start_id, "nodes": nodes, "edges": edges}


@router.get("/positions")
async def get_graph_positions(platform: str = DEFAULT_SCENARIO_PLATFORM):
    positions_path = _resolve_platform(platform)["positions_path"]
    if not positions_path.exists():
        return {}
    return json.loads(positions_path.read_text(encoding="utf-8"))


@router.put("/positions")
async def put_graph_positions(positions: dict[str, dict[str, float]], platform: str = DEFAULT_SCENARIO_PLATFORM):
    # Раскладка общая для всех, кто открывает граф, поэтому сохраняем только
    # координаты реально существующих блоков — иначе устаревшие/чужие id будут
    # копиться в файле вечно.
    resolved = _resolve_platform(platform)
    block_ids = set(json.loads(resolved["path"].read_text(encoding="utf-8"))["blocks"].keys())
    clean = {
        block_id: {"x": pos["x"], "y": pos["y"]}
        for block_id, pos in positions.items()
        if block_id in block_ids and "x" in pos and "y" in pos
    }
    resolved["positions_path"].write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}
