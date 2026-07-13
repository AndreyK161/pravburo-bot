import { escapeHtml } from "./utils.js";
import { showToast } from "./toast.js";
import { confirmModal } from "./modal.js";

const TYPE_LABELS = {
  message: "Сообщение",
  document: "Документ/файл",
  input: "Вопрос пользователю",
  condition: "Проверка подписки",
  delay: "Задержка",
};

const DEFAULT_BLOCK_TEMPLATE = {
  type: "message",
  text: "",
};

let scenario = null;
let meta = null;
let editingBlockId = null; // null => создаём новый блок

export async function loadScenario() {
  try {
    const [scenarioRes, metaRes] = await Promise.all([fetch("/api/scenario"), fetch("/api/scenario/meta")]);
    if (!scenarioRes.ok || !metaRes.ok) throw new Error("Failed to fetch scenario");
    scenario = await scenarioRes.json();
    meta = await metaRes.json();
  } catch {
    showToast("Не удалось загрузить сценарий");
    return;
  }
  renderBlockList();
  closeEditor();
}

function displayLabel(id) {
  return scenario.blocks[id]?.name || id;
}

function renderBlockList() {
  const filter = document.getElementById("blockSearch").value.trim().toLowerCase();
  const listEl = document.getElementById("blockList");
  const ids = Object.keys(scenario.blocks)
    .filter((id) => id.toLowerCase().includes(filter) || (scenario.blocks[id].name ?? "").toLowerCase().includes(filter))
    .sort((a, b) => displayLabel(a).localeCompare(displayLabel(b)));

  listEl.innerHTML = ids
    .map((id) => {
      const block = scenario.blocks[id];
      const active = id === editingBlockId ? "bg-gray-100" : "";
      const title = block.name ? escapeHtml(block.name) : escapeHtml(id);
      const subtitle = block.name ? `${escapeHtml(id)} · ${escapeHtml(TYPE_LABELS[block.type] ?? block.type)}` : escapeHtml(TYPE_LABELS[block.type] ?? block.type);
      return `
      <button type="button" class="block-list-item w-full text-left px-2 py-1.5 rounded-md hover:bg-gray-100 ${active}" data-id="${escapeHtml(id)}">
        <div class="truncate">${title}</div>
        <div class="text-xs text-gray-400 truncate">${subtitle}</div>
      </button>`;
    })
    .join("");

  listEl.querySelectorAll(".block-list-item").forEach((btn) => {
    btn.addEventListener("click", () => openEditor(btn.dataset.id));
  });
}

document.getElementById("blockSearch").addEventListener("input", renderBlockList);

document.getElementById("newBlockBtn").addEventListener("click", () => openEditor(null));

document.getElementById("cancelEditBtn").addEventListener("click", closeEditor);

function closeEditor() {
  editingBlockId = null;
  document.getElementById("blockEditorForm").classList.add("hidden");
  document.getElementById("blockEditorEmpty").classList.remove("hidden");
  renderBlockList();
}

function renderMetaHint() {
  const el = document.getElementById("scenarioMetaHint");
  el.innerHTML = `
    <div><b>type:</b> ${meta.block_types.join(", ")}</div>
    <div><b>save_as:</b> ${meta.save_as_fields.join(", ")}</div>
    <div><b>validate:</b> ${meta.validators.join(", ") || "—"}</div>
    <div><b>files:</b> ${meta.files.join(", ") || "—"}</div>
    <div><b>id блоков (для next/auto_next/yes/no/buttons):</b> ${meta.block_ids.join(", ")}</div>
  `;
}

function openEditor(blockId) {
  editingBlockId = blockId;
  const block = blockId ? scenario.blocks[blockId] : null;

  document.getElementById("blockEditorEmpty").classList.add("hidden");
  document.getElementById("blockEditorForm").classList.remove("hidden");

  const idInput = document.getElementById("fieldBlockId");
  idInput.value = blockId ?? "";
  idInput.disabled = Boolean(blockId);
  idInput.className = blockId
    ? "border rounded-md px-2 py-1 text-sm w-full bg-gray-100 text-gray-500"
    : "border rounded-md px-2 py-1 text-sm w-full";

  document.getElementById("fieldBlockJson").value = JSON.stringify(block ?? DEFAULT_BLOCK_TEMPLATE, null, 2);

  renderMetaHint();
  renderBlockList();
}

document.getElementById("blockEditorForm").addEventListener("submit", async (e) => {
  e.preventDefault();

  const newId = document.getElementById("fieldBlockId").value.trim();

  if (!editingBlockId) {
    if (!newId) {
      showToast("Укажите ID нового блока");
      return;
    }
    if (scenario.blocks[newId]) {
      showToast("Блок с таким ID уже существует");
      return;
    }
  }

  let block;
  try {
    block = JSON.parse(document.getElementById("fieldBlockJson").value);
  } catch (err) {
    showToast(`Невалидный JSON: ${err.message}`);
    return;
  }
  if (typeof block !== "object" || block === null || Array.isArray(block)) {
    showToast("JSON блока должен быть объектом");
    return;
  }

  const confirmed = await confirmModal(
    editingBlockId ? `Сохранить изменения блока '${editingBlockId}'?` : `Создать новый блок '${newId}'?`,
    "Сохранить"
  );
  if (!confirmed) return;

  const blockId = editingBlockId ?? newId;
  const updatedScenario = { ...scenario, blocks: { ...scenario.blocks, [blockId]: block } };

  try {
    const res = await fetch("/api/scenario", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updatedScenario),
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.detail ?? "Не удалось сохранить сценарий");
      return;
    }
    showToast(editingBlockId ? "Блок сохранён" : "Блок создан", "success");
    await loadScenario();
    openEditor(blockId);
  } catch {
    showToast("Не удалось сохранить сценарий: ошибка сети");
  }
});
