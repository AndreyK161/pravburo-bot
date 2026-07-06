import { loadStats } from "./stats.js";
import { loadTagFilter, loadUsers } from "./users.js";
import { loadTagsPage } from "./tags-page.js";
import { loadBroadcastTags } from "./broadcast.js";
import { loadScenario } from "./scenario.js";
import { requireLogin, currentRole } from "./auth.js";

const tabButtons = document.querySelectorAll(".tab-btn");
const tabs = {
  stats: document.getElementById("tab-stats"),
  users: document.getElementById("tab-users"),
  tags: document.getElementById("tab-tags"),
  broadcast: document.getElementById("tab-broadcast"),
  scenario: document.getElementById("tab-scenario"),
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
  if (name === "users") loadTagFilter().then(loadUsers);
  if (name === "tags") loadTagsPage();
  if (name === "broadcast") loadBroadcastTags();
  if (name === "scenario") loadScenario();
}

tabButtons.forEach((btn) => btn.addEventListener("click", () => activateTab(btn.dataset.tab)));

requireLogin().then((ok) => {
  if (!ok) return;
  if (currentRole !== "admin") {
    document.querySelector('[data-tab="scenario"]').classList.add("hidden");
  }
  activateTab("stats");
});
