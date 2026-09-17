import { loadStats } from "./stats.js";
import { loadTagFilter, loadUsers } from "./users.js";
import { loadTagsPage } from "./tags-page.js";
import { loadBroadcastTags, loadScheduledBroadcasts } from "./broadcast.js";
import { loadScenario } from "./scenario.js";
import { loadGraph, setGraphTabVisible } from "./graph/index.js";
import { requireLogin, currentRole } from "./auth.js";

const ROLE_LABELS = {
  admin: "администратор",
  manager: "менеджер",
};

const navButtons = document.querySelectorAll(".nav-item");
const tabs = {
  stats: document.getElementById("tab-stats"),
  users: document.getElementById("tab-users"),
  tags: document.getElementById("tab-tags"),
  broadcast: document.getElementById("tab-broadcast"),
  graph: document.getElementById("tab-graph"),
  scenario: document.getElementById("tab-scenario"),
};

const pageTitle = document.getElementById("pageTitle");
const pageDescription = document.getElementById("pageDescription");

function activateTab(name) {
  for (const [key, el] of Object.entries(tabs)) {
    el.classList.toggle("hidden", key !== name);
  }
  navButtons.forEach((btn) => {
    const active = btn.dataset.tab === name;
    btn.classList.toggle("active", active);
    if (active) {
      pageTitle.textContent = btn.querySelector(".font-medium")?.textContent ?? "";
      pageDescription.textContent = btn.dataset.description ?? "";
    }
  });
  if (name === "stats") loadStats();
  if (name === "users") loadTagFilter().then(loadUsers);
  if (name === "tags") loadTagsPage();
  if (name === "broadcast") {
    loadBroadcastTags();
    loadScheduledBroadcasts();
  }
  if (name === "graph") loadGraph();
  if (name === "scenario") loadScenario();
  setGraphTabVisible(name === "graph");
}

const sidebar = document.getElementById("sidebar");
const sidebarOverlay = document.getElementById("sidebarOverlay");
const sidebarToggleBtn = document.getElementById("sidebarToggleBtn");

function closeSidebar() {
  sidebar.classList.add("-translate-x-full");
  sidebarOverlay.classList.add("hidden");
  sidebarToggleBtn.setAttribute("aria-expanded", "false");
}

function openSidebar() {
  sidebar.classList.remove("-translate-x-full");
  sidebarOverlay.classList.remove("hidden");
  sidebarToggleBtn.setAttribute("aria-expanded", "true");
}

sidebarToggleBtn.addEventListener("click", () => {
  const isOpen = !sidebar.classList.contains("-translate-x-full");
  if (isOpen) closeSidebar();
  else openSidebar();
});

sidebarOverlay.addEventListener("click", closeSidebar);

navButtons.forEach((btn) =>
  btn.addEventListener("click", () => {
    activateTab(btn.dataset.tab);
    closeSidebar();
  })
);

requireLogin().then((ok) => {
  if (!ok) return;
  if (currentRole !== "admin") {
    document.querySelectorAll('[data-tab="scenario"]').forEach((el) => el.classList.add("hidden"));
  }
  const username = document.getElementById("currentUsername").textContent;
  document.getElementById("currentUserAvatar").textContent = (username || "?").slice(0, 1).toUpperCase();
  document.getElementById("currentUserRole").textContent = ROLE_LABELS[currentRole] ?? currentRole ?? "";
  activateTab("stats");
});
