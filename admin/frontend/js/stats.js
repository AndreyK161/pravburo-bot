import { escapeHtml, colorForIndex } from "./utils.js";
import { showToast } from "./toast.js";

let sourcesChart = null;
let allSourceStats = [];
let selectedSources = new Set();

export async function loadStats() {
  try {
    const res = await fetch("/api/stats/sources");
    if (!res.ok) throw new Error("Failed to fetch stats");
    allSourceStats = await res.json();
  } catch {
    showToast("Не удалось загрузить статистику");
    return;
  }
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
