import { escapeHtml } from "./utils.js";
import { fetchTags, createTag, updateTag, deleteTag } from "./tags.js";
import { showToast } from "./toast.js";
import { confirmModal } from "./modal.js";

export async function loadTagsPage() {
  let tags;
  try {
    tags = await fetchTags();
  } catch {
    showToast("Не удалось загрузить теги");
    return;
  }

  const tbody = document.getElementById("tagsTableBody");
  if (!tags.length) {
    tbody.innerHTML = '<tr><td colspan="3" class="py-3 px-3 text-gray-400">Тегов пока нет</td></tr>';
    return;
  }

  tbody.innerHTML = tags
    .map(
      (t) => `
      <tr class="border-b last:border-0" data-tag-id="${t.id}">
        <td class="py-2 px-3">
          <input type="text" value="${escapeHtml(t.name)}" maxlength="32" class="tag-rename-input border rounded-md px-2 py-1 text-sm w-56">
        </td>
        <td class="py-2 px-3">${new Date(t.created_at).toLocaleString("ru-RU")}</td>
        <td class="py-2 px-3 whitespace-nowrap">
          <button class="tag-save-btn text-sm text-blue-600 hover:underline mr-3">Сохранить</button>
          <button class="tag-delete-btn text-sm text-red-600 hover:underline">Удалить</button>
        </td>
      </tr>`
    )
    .join("");

  tbody.querySelectorAll(".tag-save-btn").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      const row = e.target.closest("[data-tag-id]");
      const tagId = Number(row.dataset.tagId);
      const input = row.querySelector(".tag-rename-input");
      const name = input.value.trim();
      if (!name) return;
      try {
        const res = await updateTag(tagId, name);
        if (res.ok) {
          showToast("Тег обновлён", "success");
          await loadTagsPage();
        } else {
          const err = await res.json();
          showToast(err.detail ?? "Не удалось обновить тег");
        }
      } catch {
        showToast("Не удалось обновить тег: ошибка сети");
      }
    });
  });

  tbody.querySelectorAll(".tag-delete-btn").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      const row = e.target.closest("[data-tag-id]");
      const tagId = Number(row.dataset.tagId);
      const tagName = row.querySelector(".tag-rename-input").value;
      const confirmed = await confirmModal(`Удалить тег "${tagName}"? Он будет снят у всех пользователей.`, "Удалить");
      if (!confirmed) return;
      try {
        const res = await deleteTag(tagId);
        if (res.ok) {
          showToast("Тег удалён", "success");
          await loadTagsPage();
        } else {
          const err = await res.json();
          showToast(err.detail ?? "Не удалось удалить тег");
        }
      } catch {
        showToast("Не удалось удалить тег: ошибка сети");
      }
    });
  });
}

document.getElementById("createTagBtn").addEventListener("click", async () => {
  const input = document.getElementById("newTagName");
  const name = input.value.trim();
  if (!name) return;

  try {
    const res = await createTag(name);
    if (res.ok) {
      input.value = "";
      showToast("Тег создан", "success");
      await loadTagsPage();
    } else {
      const err = await res.json();
      showToast(err.detail ?? "Не удалось создать тег");
    }
  } catch {
    showToast("Не удалось создать тег: ошибка сети");
  }
});
