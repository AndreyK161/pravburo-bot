import { loadStats } from "./stats.js";
import { loadTagFilter, loadUsers } from "./users.js";
import { loadTagsPage } from "./tags-page.js";
import { loadBroadcastTags, loadScheduledBroadcasts } from "./broadcast.js";
import { loadScenario } from "./scenario.js";
import { loadGraph, setGraphTabVisible } from "./graph/index.js";
import { requireLogin, currentRole } from "./auth.js";

const tabButtons = document.querySelectorAll(".tab-btn");
const tabs = {
  stats: document.getElementById("tab-stats"),
  users: document.getElementById("tab-users"),
  tags: document.getElementById("tab-tags"),
  broadcast: document.getElementById("tab-broadcast"),
  graph: document.getElementById("tab-graph"),
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
  if (name === "broadcast") {
    loadBroadcastTags();
    loadScheduledBroadcasts();
  }
  if (name === "graph") loadGraph();
  if (name === "scenario") loadScenario();
  setGraphTabVisible(name === "graph");
}

const mobileMenu = document.getElementById("mobileMenu");
const mobileMenuBtn = document.getElementById("mobileMenuBtn");
const mobileMenuIconOpen = document.getElementById("mobileMenuIconOpen");
const mobileMenuIconClose = document.getElementById("mobileMenuIconClose");

function closeMobileMenu() {
  mobileMenu.classList.add("hidden");
  mobileMenuIconOpen.classList.remove("hidden");
  mobileMenuIconClose.classList.add("hidden");
  mobileMenuBtn.setAttribute("aria-expanded", "false");
}

mobileMenuBtn.addEventListener("click", () => {
  const isOpen = !mobileMenu.classList.contains("hidden");
  if (isOpen) {
    closeMobileMenu();
  } else {
    mobileMenu.classList.remove("hidden");
    mobileMenuIconOpen.classList.add("hidden");
    mobileMenuIconClose.classList.remove("hidden");
    mobileMenuBtn.setAttribute("aria-expanded", "true");
  }
});

tabButtons.forEach((btn) =>
  btn.addEventListener("click", () => {
    activateTab(btn.dataset.tab);
    closeMobileMenu();
  })
);

requireLogin().then((ok) => {
  if (!ok) return;
  if (currentRole !== "admin") {
    document.querySelectorAll('[data-tab="scenario"]').forEach((el) => el.classList.add("hidden"));
  }
  activateTab("stats");
});
