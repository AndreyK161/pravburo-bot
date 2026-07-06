const tabButtons = document.querySelectorAll(".tab-btn");
const tabs = {
  stats: document.getElementById("tab-stats"),
  users: document.getElementById("tab-users"),
};

function activateTab(name) {
  for (const [key, el] of Object.entries(tabs)) {
    el.classList.toggle("hidden", key !== name);
  }
  tabButtons.forEach((btn) => {
    const active = btn.dataset.tab === name;
    btn.classList.toggle("bg-gray-900", active);
    btn.classList.toggle("text-white", active);
    btn.classList.toggle("text-gray-600", !active);
  });
  if (name === "stats") loadStats();
  if (name === "users") loadTags().then(loadUsers);
}

tabButtons.forEach((btn) => btn.addEventListener("click", () => activateTab(btn.dataset.tab)));

let sourcesChart = null;
let allSourceStats = [];
let selectedSources = new Set();

async function loadStats() {
  const res = await fetch("/api/stats/sources");
  allSourceStats = await res.json();
  selectedSources = new Set(allSourceStats.map((r) => r.source));

  const checkboxesEl = document.getElementById("sourcesCheckboxes");
  checkboxesEl.innerHTML = allSourceStats
    .map(
      (row, i) => `
      <label class="flex items-center gap-1.5 cursor-pointer">
        <input type="checkbox" class="source-checkbox" value="${escapeHtml(row.source)}" checked
               style="accent-color: ${colorForIndex(i)}">
        ${escapeHtml(row.source)}
      </label>`
    )
    .join("");

  checkboxesEl.querySelectorAll(".source-checkbox").forEach((cb) => {
    cb.addEventListener("change", () => {
      if (cb.checked) selectedSources.add(cb.value);
      else selectedSources.delete(cb.value);
      renderStats();
    });
  });

  renderStats();
}

document.getElementById("sourcesSelectAll").addEventListener("click", () => {
  selectedSources = new Set(allSourceStats.map((r) => r.source));
  document.querySelectorAll(".source-checkbox").forEach((cb) => (cb.checked = true));
  renderStats();
});

document.getElementById("sourcesSelectNone").addEventListener("click", () => {
  selectedSources.clear();
  document.querySelectorAll(".source-checkbox").forEach((cb) => (cb.checked = false));
  renderStats();
});

function renderStats() {
  const rows = allSourceStats.filter((r) => selectedSources.has(r.source));

  const tbody = document.getElementById("sourcesTableBody");
  tbody.innerHTML = rows
    .map(
      (row) => `
      <tr class="border-b last:border-0">
        <td class="py-2">${escapeHtml(row.source)}</td>
        <td class="py-2">${row.users_count}</td>
      </tr>`
    )
    .join("");

  const ctx = document.getElementById("sourcesChart");
  const data = {
    labels: rows.map((r) => r.source),
    datasets: [
      {
        label: "Пользователей",
        data: rows.map((r) => r.users_count),
        backgroundColor: rows.map((r) => colorForIndex(allSourceStats.indexOf(r))),
      },
    ],
  };
  if (sourcesChart) {
    sourcesChart.data = data;
    sourcesChart.update();
  } else {
    sourcesChart = new Chart(ctx, { type: "bar", data, options: { plugins: { legend: { display: false } } } });
  }
}

let allTags = [];

async function loadTags() {
  const res = await fetch("/api/tags");
  allTags = await res.json();

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
  return `<select class="border rounded-md px-1.5 py-0.5 text-xs user-tag-select">${options}</select>`;
}

const PAGE_SIZE = 20;
let currentPage = 1;

async function loadUsers() {
  const tagId = document.getElementById("tagFilter").value;
  const field = document.getElementById("userSearchField").value;
  const value = document.getElementById("userSearch").value.trim();

  const params = new URLSearchParams({ page: currentPage, page_size: PAGE_SIZE });
  if (tagId) params.set("tag_id", tagId);
  if (value) {
    params.set("field", field);
    params.set("value", value);
  }

  const res = await fetch(`/api/users?${params}`);
  const { items: users, total, page, page_size } = await res.json();

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
        <td class="py-2 px-3">${tagSelectHtml(u.tag_id)}</td>
        <td class="py-2 px-3">${new Date(u.created_at).toLocaleString("ru-RU")}</td>
      </tr>`
    )
    .join("");

  tbody.querySelectorAll(".user-tag-select").forEach((select) => {
    select.addEventListener("change", async (e) => {
      const row = e.target.closest("tr");
      const userId = row.dataset.userId;
      const tagId = e.target.value ? Number(e.target.value) : null;
      await fetch(`/api/users/${userId}/tag`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tag_id: tagId }),
      });
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

document.getElementById("createTagBtn").addEventListener("click", async () => {
  const input = document.getElementById("newTagName");
  const name = input.value.trim();
  if (!name) return;
  const res = await fetch("/api/tags", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (res.ok) {
    input.value = "";
    await loadTags();
    await loadUsers();
  } else {
    const err = await res.json();
    alert(err.detail ?? "Не удалось создать тег");
  }
});

const CHART_COLORS = ["#1f2937", "#2563eb", "#16a34a", "#d97706", "#dc2626", "#7c3aed", "#0891b2", "#db2777"];

function colorForIndex(i) {
  return CHART_COLORS[i % CHART_COLORS.length];
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

activateTab("stats");
