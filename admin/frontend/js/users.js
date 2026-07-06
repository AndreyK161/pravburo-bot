import { escapeHtml } from "./utils.js";
import { fetchTags } from "./tags.js";
import { showToast } from "./toast.js";

const PAGE_SIZE = 20;
let currentPage = 1;
let allTags = [];

export async function loadTagFilter() {
  try {
    allTags = await fetchTags();
  } catch {
    showToast("Не удалось загрузить теги");
    return;
  }
  const filterOptions = ['<option value="">Все</option>']
    .concat(allTags.map((t) => `<option value="${t.id}">${escapeHtml(t.name)}</option>`))
    .join("");
  document.getElementById("tagFilter").innerHTML = filterOptions;
}

function tagSelectHtml(userTagId) {
  const options = ['<option value="">—</option>']
    .concat(
      allTags.map(
        (t) => `<option value="${t.id}" ${t.id === userTagId ? "selected" : ""}>${escapeHtml(t.name)}</option>`
      )
    )
    .join("");
  return `<select class="border rounded-md px-1.5 py-0.5 text-xs user-tag-select" data-previous-value="${userTagId ?? ""}">${options}</select>`;
}

export async function loadUsers() {
  const tagId = document.getElementById("tagFilter").value;
  const field = document.getElementById("userSearchField").value;
  const value = document.getElementById("userSearch").value.trim();

  const params = new URLSearchParams({ page: currentPage, page_size: PAGE_SIZE });
  if (tagId) params.set("tag_id", tagId);
  if (value) {
    params.set("field", field);
    params.set("value", value);
  }

  let payload;
  try {
    const res = await fetch(`/api/users?${params}`);
    if (!res.ok) throw new Error("Failed to fetch users");
    payload = await res.json();
  } catch {
    showToast("Не удалось загрузить список пользователей");
    return;
  }
  const { items: users, total, page, page_size } = payload;

  const tbody = document.getElementById("usersTableBody");
  tbody.innerHTML = users
    .map(
      (u) => `
      <tr class="border-b last:border-0" data-user-id="${u.user_id}">
        <td class="py-2 px-3">${u.user_id}</td>
        <td class="py-2 px-3">${escapeHtml(u.username ?? "")}</td>
        <td class="py-2 px-3">${escapeHtml(u.name ?? "")}</td>
        <td class="py-2 px-3">${escapeHtml(u.phone ?? "")}</td>
        <td class="py-2 px-3">${escapeHtml(u.region ?? "")}</td>
        <td class="py-2 px-3">${escapeHtml(u.source ?? "")}</td>
        <td class="py-2 px-3 max-w-[160px] truncate" title="${escapeHtml(u.current_stage ?? "")}">${escapeHtml(u.current_stage ?? "")}</td>
        <td class="py-2 px-3">${tagSelectHtml(u.tag_id)}</td>
        <td class="py-2 px-3">${new Date(u.created_at).toLocaleString("ru-RU")}</td>
      </tr>`
    )
    .join("");

  tbody.querySelectorAll(".user-tag-select").forEach((select) => {
    select.addEventListener("change", async (e) => {
      const row = e.target.closest("tr");
      const userId = row.dataset.userId;
      const previousValue = e.target.dataset.previousValue ?? "";
      const tagId = e.target.value ? Number(e.target.value) : null;
      try {
        const res = await fetch(`/api/users/${userId}/tag`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tag_id: tagId }),
        });
        if (!res.ok) throw new Error("Failed to assign tag");
        e.target.dataset.previousValue = e.target.value;
      } catch {
        showToast("Не удалось назначить тег");
        e.target.value = previousValue;
      }
    });
  });

  const from = total === 0 ? 0 : (page - 1) * page_size + 1;
  const to = Math.min(page * page_size, total);
  document.getElementById("usersRangeLabel").textContent = `Показано ${from}–${to} из ${total}`;

  const totalPages = Math.max(Math.ceil(total / page_size), 1);
  document.getElementById("pageLabel").textContent = `Страница ${page} из ${totalPages}`;
  document.getElementById("prevPageBtn").disabled = page <= 1;
  document.getElementById("nextPageBtn").disabled = page >= totalPages;
}

document.getElementById("tagFilter").addEventListener("change", () => {
  currentPage = 1;
  loadUsers();
});

let searchDebounceTimer = null;
document.getElementById("userSearch").addEventListener("input", () => {
  clearTimeout(searchDebounceTimer);
  searchDebounceTimer = setTimeout(() => {
    currentPage = 1;
    loadUsers();
  }, 300);
});

document.getElementById("userSearchField").addEventListener("change", () => {
  currentPage = 1;
  loadUsers();
});

document.getElementById("prevPageBtn").addEventListener("click", () => {
  if (currentPage > 1) {
    currentPage -= 1;
    loadUsers();
  }
});

document.getElementById("nextPageBtn").addEventListener("click", () => {
  currentPage += 1;
  loadUsers();
});

