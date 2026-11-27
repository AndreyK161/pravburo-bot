const storageKey = "pravburo:garland-enabled";
const header = document.querySelector(".admin-header");
const garland = document.createElement("div");
garland.className = "new-year-garland";

const bulbs = ["rose", "gold", "mint", "ice"].map((color, index) => {
  const x = 30 + index * 60;
  const angle = index % 2 === 0 ? 12 : -12;
  return `
    <g transform="translate(${x} 17) rotate(${angle})">
      <path class="new-year-garland__socket" d="M-3-2h6v6h-6z" />
      <g class="new-year-garland__bulb new-year-garland__bulb--${color}">
        <ellipse class="new-year-garland__halo new-year-garland__halo--${index}" cy="10" rx="17" ry="17" />
        <path class="new-year-garland__glass" d="M-3 3C-5 6-6 10-4 14Q0 20 4 14C6 10 5 6 3 3Z" />
        <path class="new-year-garland__shine" d="M-1 6Q-3 9-2 12" />
      </g>
    </g>`;
}).join("");

garland.innerHTML = `
  <svg class="new-year-garland__lights" width="100%" height="48" aria-hidden="true">
    <defs>
      <pattern id="admin-garland-pattern" width="240" height="48" patternUnits="userSpaceOnUse">
        <path class="new-year-garland__wire" d="M-120 4 Q0 39 120 4 Q240 39 360 4" />
        ${bulbs}
      </pattern>
    </defs>
    <rect width="100%" height="48" fill="url(#admin-garland-pattern)" />
  </svg>
  <button type="button" class="new-year-garland__switch" aria-label="Новогодняя гирлянда">
    <span class="new-year-garland__cord" aria-hidden="true"></span>
    <span class="new-year-garland__handle" aria-hidden="true"><span></span></span>
    <span class="new-year-garland__tooltip" aria-hidden="true"></span>
  </button>`;

header.prepend(garland);
const button = garland.querySelector("button");
const tooltip = garland.querySelector(".new-year-garland__tooltip");
let enabled = true;
try {
  enabled = localStorage.getItem(storageKey) !== "false";
} catch {
  // The switch also works when browser storage is unavailable.
}

function render() {
  garland.dataset.enabled = String(enabled);
  button.setAttribute("aria-pressed", String(enabled));
  tooltip.textContent = enabled ? "Погасить огоньки" : "Зажечь огоньки";
}

button.addEventListener("click", () => {
  enabled = !enabled;
  render();
  try {
    localStorage.setItem(storageKey, String(enabled));
  } catch {
    // Keep the selected state for the current page.
  }
});
button.addEventListener("pointerdown", (event) => {
  if (event.button !== 0) return;
  button.setPointerCapture(event.pointerId);
  button.dataset.pulling = "true";
});
button.addEventListener("keydown", (event) => {
  if (event.key === " " || event.key === "Enter") button.dataset.pulling = "true";
});
for (const eventName of ["pointerup", "pointercancel", "lostpointercapture", "keyup", "blur"]) {
  button.addEventListener(eventName, () => { button.dataset.pulling = "false"; });
}
render();
