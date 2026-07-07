import { escapeHtml } from "../utils.js";

export const TYPE_COLORS = {
  message: "#2563eb",
  document: "#7c3aed",
  input: "#d97706",
  condition: "#dc2626",
  delay: "#6b7280",
};

export function renderLegend(graphData) {
  const legend = document.getElementById("scenarioGraphLegend");
  const typeItems = Object.entries(TYPE_COLORS)
    .map(
      ([type, color]) => `
      <span class="inline-flex items-center gap-1.5">
        <span class="inline-block w-2.5 h-2.5 rounded-full" style="background:${color}"></span>
        ${escapeHtml(typeLabelByType(graphData, type))}
      </span>`
    )
    .join("");

  legend.innerHTML = `
    <span class="text-gray-400">Цвет = тип блока:</span>
    ${typeItems}
    <span class="inline-flex items-center gap-1.5 ml-2 pl-2 border-l">
      <span class="inline-block w-2.5 h-2.5 rounded-full bg-white border-2" style="border-color:#16a34a"></span>
      Стартовый блок
    </span>
  `;
}

function typeLabelByType(graphData, type) {
  const node = graphData.nodes.find((n) => n.type === type);
  return node ? node.type_label : type;
}

function wrapLabel(text, maxLineLength = 16) {
  const words = text.split(" ");
  const lines = [];
  let line = "";
  for (const word of words) {
    const candidate = line ? `${line} ${word}` : word;
    if (candidate.length > maxLineLength && line) {
      lines.push(line);
      line = word;
    } else {
      line = candidate;
    }
  }
  if (line) lines.push(line);
  return lines.join("\n");
}

export function nodeDataset(graphData, savedPositions) {
  return graphData.nodes.map((n) => ({
    id: n.id,
    label: wrapLabel(n.label),
    shape: "dot",
    size: n.is_start ? 22 : 14,
    color: {
      background: TYPE_COLORS[n.type] ?? "#6b7280",
      border: n.is_start ? "#16a34a" : TYPE_COLORS[n.type] ?? "#6b7280",
    },
    borderWidth: n.is_start ? 3 : 1,
    font: { size: 12, color: "#1f2937", multi: false, vadjust: 0 },
    margin: 8,
    ...(savedPositions?.[n.id] ?? {}),
  }));
}

export function edgeDataset(graphData) {
  return graphData.edges.map((e) => ({
    from: e.from,
    to: e.to,
    label: e.label ?? "",
    arrows: "to",
    font: { size: 10, color: "#6b7280", strokeWidth: 8, strokeColor: "#ffffff", align: "top" },
    color: { color: "#cbd5e1", highlight: "#94a3b8" },
    smooth: { type: "continuous" },
  }));
}

export function renderDetail(network, graphData, nodeId) {
  const node = graphData.nodes.find((n) => n.id === nodeId);
  if (!node) return;

  document.getElementById("graphDetailEmpty").classList.add("hidden");
  const content = document.getElementById("graphDetailContent");
  content.classList.remove("hidden");

  const incoming = graphData.edges.filter((e) => e.to === nodeId);
  const outgoing = graphData.edges.filter((e) => e.from === nodeId);
  const labelOf = (id) => graphData.nodes.find((n) => n.id === id)?.label ?? id;

  content.innerHTML = `
    <div>
      <h3 class="font-semibold text-base">${escapeHtml(node.label)}</h3>
      <div class="flex flex-wrap gap-1.5 mt-1.5">
        <span class="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-700">${escapeHtml(node.type_label)}</span>
        ${node.is_start ? '<span class="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">Начало сценария</span>' : ""}
        ${node.auto_tag ? `<span class="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">Тег: ${escapeHtml(node.auto_tag)}</span>` : ""}
      </div>
    </div>

    ${node.preview ? `<p class="text-gray-700 whitespace-pre-line border-t pt-3">${escapeHtml(node.preview)}</p>` : ""}

    ${
      node.buttons.length
        ? `<div class="border-t pt-3">
            <div class="text-xs text-gray-500 mb-1">Кнопки:</div>
            <ul class="space-y-1">
              ${node.buttons
                .map(
                  (b) =>
                    `<li class="flex flex-wrap items-center justify-between gap-x-2 gap-y-0.5">
                      <span class="break-words min-w-0">${escapeHtml(b.text)}</span>
                      <button class="graph-jump text-blue-600 hover:underline text-xs break-words text-right" data-target="${b.next}">→ ${escapeHtml(labelOf(b.next))}</button>
                    </li>`
                )
                .join("")}
            </ul>
          </div>`
        : ""
    }

    ${
      outgoing.length && !node.buttons.length
        ? `<div class="border-t pt-3">
            <div class="text-xs text-gray-500 mb-1">Переходит в:</div>
            <ul class="space-y-1">
              ${outgoing
                .map(
                  (e) =>
                    `<li class="flex flex-wrap items-center justify-between gap-x-2 gap-y-0.5">
                      <span class="text-gray-500 break-words min-w-0">${e.label ? escapeHtml(e.label) : "далее"}</span>
                      <button class="graph-jump text-blue-600 hover:underline text-xs break-words text-right" data-target="${e.to}">→ ${escapeHtml(labelOf(e.to))}</button>
                    </li>`
                )
                .join("")}
            </ul>
          </div>`
        : ""
    }

    ${
      incoming.length
        ? `<div class="border-t pt-3">
            <div class="text-xs text-gray-500 mb-1">Приходят из:</div>
            <ul class="space-y-1">
              ${incoming
                .map(
                  (e) =>
                    `<li>
                      <button class="graph-jump text-blue-600 hover:underline text-xs break-words text-left" data-target="${e.from}">← ${escapeHtml(labelOf(e.from))}</button>
                    </li>`
                )
                .join("")}
            </ul>
          </div>`
        : ""
    }
  `;

  content.querySelectorAll(".graph-jump").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.dataset.target;
      network.selectNodes([targetId]);
      network.focus(targetId, { scale: 1, animation: { duration: 400, easingFunction: "easeInOutQuad" } });
      renderDetail(network, graphData, targetId);
    });
  });
}
