import { escapeHtml } from "./utils.js";
import { fetchTags } from "./tags.js";
import { showToast } from "./toast.js";
import { confirmModal } from "./modal.js";

export async function loadBroadcastTags() {
  let tags;
  try {
    tags = await fetchTags();
  } catch {
    showToast("Не удалось загрузить теги");
    return;
  }
  const select = document.getElementById("broadcastTag");
  select.innerHTML = ['<option value="">Всем пользователям</option>']
    .concat(tags.map((t) => `<option value="${t.id}">Тег: ${escapeHtml(t.name)}</option>`))
    .join("");
}

document.getElementById("broadcastSendBtn").addEventListener("click", async () => {
  const text = document.getElementById("broadcastText").value.trim();
  const tagId = document.getElementById("broadcastTag").value;
  const resultEl = document.getElementById("broadcastResult");

  if (!text) {
    resultEl.textContent = "Введите текст сообщения";
    resultEl.className = "text-sm text-red-600";
    return;
  }

  const targetLabel = tagId
    ? document.getElementById("broadcastTag").selectedOptions[0].textContent
    : "всем пользователям";
  const confirmed = await confirmModal(
    `Отправить рассылку ${targetLabel}?\n\nЭто действие необратимо.`,
    "Отправить"
  );
  if (!confirmed) return;

  const btn = document.getElementById("broadcastSendBtn");
  btn.disabled = true;
  btn.textContent = "Отправка...";
  resultEl.textContent = "";

  try {
    const res = await fetch("/api/broadcast", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, tag_id: tagId ? Number(tagId) : null }),
    });
    const data = await res.json();
    if (res.ok) {
      resultEl.className = "text-sm text-gray-700";
      resultEl.textContent = `Готово: доставлено ${data.sent} из ${data.total}, заблокировали бота ${data.blocked}, ошибок ${data.failed}.`;
    } else {
      resultEl.className = "text-sm text-red-600";
      resultEl.textContent = data.detail ?? "Не удалось отправить рассылку";
    }
  } catch {
    showToast("Не удалось отправить рассылку: ошибка сети");
  } finally {
    btn.disabled = false;
    btn.textContent = "Отправить рассылку";
  }
});
