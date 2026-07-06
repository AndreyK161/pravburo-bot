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

function blockIdOptions(selected, includeEmpty) {
  const options = includeEmpty ? ['<option value="">— нет —</option>'] : [];
  const sortedIds = [...meta.block_ids].sort((a, b) => displayLabel(a).localeCompare(displayLabel(b)));
  options.push(
    ...sortedIds.map((id) => `<option value="${escapeHtml(id)}" ${id === selected ? "selected" : ""}>${escapeHtml(displayLabel(id))}</option>`)
  );
  return options.join("");
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

  document.getElementById("fieldBlockName").value = block?.name ?? "";

  const typeSelect = document.getElementById("fieldType");
  typeSelect.innerHTML = meta.block_types
    .map((t) => `<option value="${t}">${escapeHtml(TYPE_LABELS[t] ?? t)}</option>`)
    .join("");
  typeSelect.value = block ? block.type : meta.block_types[0];

  renderDynamicFields(typeSelect.value, block);
  renderBlockList();
}

document.getElementById("fieldType").addEventListener("change", (e) => {
  renderDynamicFields(e.target.value, null);
});

function renderButtonsEditorHtml(buttons) {
  const rows = (buttons ?? [])
    .map(
      (btn, i) => `
      <div class="button-row flex items-center gap-2" data-index="${i}">
        <input type="text" class="button-text border rounded-md px-2 py-1 text-sm flex-1" placeholder="Текст кнопки" value="${escapeHtml(btn.text ?? "")}">
        <select class="button-next border rounded-md px-2 py-1 text-sm flex-1">${blockIdOptions(btn.next, false)}</select>
        <button type="button" class="button-remove text-red-600 text-sm px-2">✕</button>
      </div>`
    )
    .join("");

  return `
    <div>
      <label class="text-sm text-gray-600 block mb-1">Кнопки</label>
      <div id="buttonsRows" class="space-y-2">${rows}</div>
      <button type="button" id="addButtonRow" class="text-blue-600 text-sm mt-2">+ добавить кнопку</button>
    </div>`;
}

function wireButtonsEditor() {
  const container = document.getElementById("dynamicFields");
  const rowsEl = container.querySelector("#buttonsRows");
  const addBtn = container.querySelector("#addButtonRow");
  if (!rowsEl || !addBtn) return;

  function wireRow(row) {
    row.querySelector(".button-remove").addEventListener("click", () => row.remove());
  }
  rowsEl.querySelectorAll(".button-row").forEach(wireRow);

  addBtn.addEventListener("click", () => {
    const row = document.createElement("div");
    row.className = "button-row flex items-center gap-2";
    row.innerHTML = `
      <input type="text" class="button-text border rounded-md px-2 py-1 text-sm flex-1" placeholder="Текст кнопки">
      <select class="button-next border rounded-md px-2 py-1 text-sm flex-1">${blockIdOptions(null, false)}</select>
      <button type="button" class="button-remove text-red-600 text-sm px-2">✕</button>`;
    rowsEl.appendChild(row);
    wireRow(row);
  });
}

function renderDynamicFields(type, block) {
  const container = document.getElementById("dynamicFields");
  let html = "";

  if (type === "message" || type === "document" || type === "input") {
    html += `
      <div>
        <label class="text-sm text-gray-600 block mb-1">Текст <span class="text-red-600">*</span></label>
        <textarea id="fieldText" rows="4" class="border rounded-md px-2 py-1.5 text-sm w-full">${escapeHtml(block?.text ?? "")}</textarea>
      </div>`;
  }

  if (type === "document") {
    const selectedFiles = block ? (Array.isArray(block.file) ? block.file : [block.file]) : [];
    html += `
      <div>
        <label class="text-sm text-gray-600 block mb-1">Файл(ы) <span class="text-red-600">*</span></label>
        <div id="fieldFiles" class="border rounded-md p-2 max-h-40 overflow-y-auto space-y-1">
          ${meta.files
            .map(
              (name) => `
            <label class="flex items-center gap-2 text-sm">
              <input type="checkbox" value="${escapeHtml(name)}" ${selectedFiles.includes(name) ? "checked" : ""}>
              ${escapeHtml(name)}
            </label>`
            )
            .join("")}
        </div>
      </div>`;
  }

  if (type === "input") {
    html += `
      <div>
        <label class="text-sm text-gray-600 block mb-1">Сохранить как (save_as) <span class="text-red-600">*</span></label>
        <select id="fieldSaveAs" class="border rounded-md px-2 py-1 text-sm w-full">
          ${meta.save_as_fields.map((f) => `<option value="${f}" ${block?.save_as === f ? "selected" : ""}>${f}</option>`).join("")}
        </select>
      </div>
      <div>
        <label class="text-sm text-gray-600 block mb-1">Валидация</label>
        <select id="fieldValidate" class="border rounded-md px-2 py-1 text-sm w-full">
          <option value="">— нет —</option>
          ${meta.validators.map((v) => `<option value="${v}" ${block?.validate === v ? "selected" : ""}>${v}</option>`).join("")}
        </select>
      </div>
      <div>
        <label class="text-sm text-gray-600 block mb-1">Следующий блок (next) <span class="text-red-600">*</span></label>
        <select id="fieldNext" class="border rounded-md px-2 py-1 text-sm w-full">${blockIdOptions(block?.next, false)}</select>
      </div>`;
  }

  if (type === "message" || type === "document") {
    html += `
      <div>
        <label class="text-sm text-gray-600 block mb-1">Автопереход (auto_next)</label>
        <select id="fieldAutoNext" class="border rounded-md px-2 py-1 text-sm w-full">${blockIdOptions(block?.auto_next, true)}</select>
      </div>`;
  }

  if (type === "condition") {
    html += `
      <div>
        <label class="text-sm text-gray-600 block mb-1">Канал (channel) <span class="text-red-600">*</span></label>
        <input id="fieldChannel" type="text" class="border rounded-md px-2 py-1 text-sm w-full" value="${escapeHtml(block?.channel ?? "")}" placeholder="@channel_username">
      </div>
      <div>
        <label class="text-sm text-gray-600 block mb-1">Если подписан (yes) <span class="text-red-600">*</span></label>
        <select id="fieldYes" class="border rounded-md px-2 py-1 text-sm w-full">${blockIdOptions(block?.yes, false)}</select>
      </div>
      <div>
        <label class="text-sm text-gray-600 block mb-1">Если не подписан (no) <span class="text-red-600">*</span></label>
        <select id="fieldNo" class="border rounded-md px-2 py-1 text-sm w-full">${blockIdOptions(block?.no, false)}</select>
      </div>`;
  }

  if (type === "delay") {
    html += `
      <div>
        <label class="text-sm text-gray-600 block mb-1">Секунды <span class="text-red-600">*</span></label>
        <input id="fieldSeconds" type="number" min="1" class="border rounded-md px-2 py-1 text-sm w-full" value="${block?.seconds ?? ""}">
      </div>
      <div>
        <label class="text-sm text-gray-600 block mb-1">Следующий блок (next) <span class="text-red-600">*</span></label>
        <select id="fieldNext" class="border rounded-md px-2 py-1 text-sm w-full">${blockIdOptions(block?.next, false)}</select>
      </div>`;
  }

  if (type === "message" || type === "document" || type === "input") {
    html += renderButtonsEditorHtml(block?.buttons);
  }

  container.innerHTML = html;
  wireButtonsEditor();
}

function collectButtons() {
  return Array.from(document.querySelectorAll("#buttonsRows .button-row")).map((row) => ({
    text: row.querySelector(".button-text").value.trim(),
    next: row.querySelector(".button-next").value,
  }));
}

function buildBlockFromForm(type) {
  const block = { type };

  if (type === "message" || type === "document" || type === "input") {
    block.text = document.getElementById("fieldText").value.trim();
  }

  if (type === "document") {
    const files = Array.from(document.querySelectorAll("#fieldFiles input:checked")).map((cb) => cb.value);
    if (files.length === 0) return { error: "Выберите хотя бы один файл" };
    block.file = files.length === 1 ? files[0] : files;
  }

  if (type === "input") {
    block.save_as = document.getElementById("fieldSaveAs").value;
    const validate = document.getElementById("fieldValidate").value;
    if (validate) block.validate = validate;
    block.next = document.getElementById("fieldNext").value;
  }

  if (type === "message" || type === "document") {
    const autoNext = document.getElementById("fieldAutoNext").value;
    if (autoNext) block.auto_next = autoNext;
  }

  if (type === "condition") {
    block.channel = document.getElementById("fieldChannel").value.trim();
    block.yes = document.getElementById("fieldYes").value;
    block.no = document.getElementById("fieldNo").value;
  }

  if (type === "delay") {
    const seconds = Number(document.getElementById("fieldSeconds").value);
    if (!seconds || seconds <= 0) return { error: "Укажите положительное число секунд" };
    block.seconds = seconds;
    block.next = document.getElementById("fieldNext").value;
  }

  if (type === "message" || type === "document" || type === "input") {
    const buttons = collectButtons();
    if (buttons.some((b) => !b.text || !b.next)) return { error: "У каждой кнопки должны быть текст и переход" };
    if (buttons.length > 0) block.buttons = buttons;
  }

  const requiredText = ["message", "document", "input"].includes(type);
  if (requiredText && !block.text) return { error: "Заполните текст блока" };
  if (type === "condition" && !block.channel) return { error: "Заполните канал" };

  return { block };
}

document.getElementById("blockEditorForm").addEventListener("submit", async (e) => {
  e.preventDefault();

  const newId = document.getElementById("fieldBlockId").value.trim();
  const type = document.getElementById("fieldType").value;

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

  const { block, error } = buildBlockFromForm(type);
  if (error) {
    showToast(error);
    return;
  }

  const name = document.getElementById("fieldBlockName").value.trim();
  if (name) block.name = name;

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
