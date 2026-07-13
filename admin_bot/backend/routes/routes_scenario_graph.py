import json

from fastapi import APIRouter

from config import (
    CONSULTATION_DONE_BLOCK,
    CONSULTATION_START_BLOCK,
    SCENARIO_GRAPH_POSITIONS_PATH,
    SCENARIO_PATH,
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


def _clean_text(text: str | None) -> str | None:
    if not text:
        return None
    return text.strip()


@router.get("")
async def get_scenario_graph():
    scenario = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
    blocks = scenario["blocks"]
    start_id = scenario["start"]

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
                "buttons": [{"text": b["text"], "next": b["next"]} for b in block.get("buttons", [])],
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
                edges.append({"from": block_id, "to": button["next"], "label": button["text"]})

    return {"start": start_id, "nodes": nodes, "edges": edges}


@router.get("/positions")
async def get_graph_positions():
    if not SCENARIO_GRAPH_POSITIONS_PATH.exists():
        return {}
    return json.loads(SCENARIO_GRAPH_POSITIONS_PATH.read_text(encoding="utf-8"))


@router.put("/positions")
async def put_graph_positions(positions: dict[str, dict[str, float]]):
    # Раскладка общая для всех, кто открывает граф, поэтому сохраняем только
    # координаты реально существующих блоков — иначе устаревшие/чужие id будут
    # копиться в файле вечно.
    block_ids = set(json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))["blocks"].keys())
    clean = {
        block_id: {"x": pos["x"], "y": pos["y"]}
        for block_id, pos in positions.items()
        if block_id in block_ids and "x" in pos and "y" in pos
    }
    SCENARIO_GRAPH_POSITIONS_PATH.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}
