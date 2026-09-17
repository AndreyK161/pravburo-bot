import { escapeHtml } from "./utils.js";

// Разные боты — разные сценарии (сейчас TG+VK делят один файл, Instagram-бота
// ещё нет, но переключалка уже готова его принять — см. config.py SCENARIO_PLATFORMS
// на бэкенде). Общее состояние для вкладок "Граф сценария" и "Сценарий", чтобы
// переключение платформы в одной вкладке сразу отражалось в другой.
let platforms = [{ id: "tg_vk", label: "TG / VK" }];
let current = "tg_vk";
let loaded = false;
const listeners = new Set();

export function getScenarioPlatform() {
  return current;
}

export function onScenarioPlatformChange(fn) {
  listeners.add(fn);
}

export async function loadScenarioPlatforms() {
  // Модуль общий для вкладок "Граф сценария" и "Сценарий" — грузим список
  // и дефолт только один раз, иначе второй вызов (при первом открытии другой
  // вкладки) сбрасывает уже выбранную пользователем платформу обратно на дефолт.
  if (loaded) return platforms;
  loaded = true;
  try {
    const res = await fetch("/api/scenario/platforms");
    if (!res.ok) throw new Error("failed");
    const data = await res.json();
    platforms = data.platforms;
    current = data.default;
  } catch {
    // остаёмся на единственном дефолтном варианте — не критично
  }
  return platforms;
}

function setScenarioPlatform(id) {
  if (id === current) return;
  current = id;
  listeners.forEach((fn) => fn(id));
}

export function renderPlatformSwitcher(container) {
  function render() {
    container.innerHTML = platforms
      .map(
        (p) => `
        <button type="button" data-platform-toggle="${p.id === current}" data-platform-id="${escapeHtml(p.id)}" class="platform-toggle">
          ${escapeHtml(p.label)}
        </button>`
      )
      .join("");
    container.querySelectorAll("[data-platform-id]").forEach((btn) => {
      btn.addEventListener("click", () => setScenarioPlatform(btn.dataset.platformId));
    });
  }
  render();
  onScenarioPlatformChange(render);
}
