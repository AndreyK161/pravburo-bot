import { escapeHtml } from "../utils.js";

export const TYPE_COLORS = {
  message: "#2563eb",
  document: "#7c3aed",
  input: "#d97706",
  condition: "#dc2626",
  delay: "#6b7280",
  video: "#0891b2",
  video_note: "#0891b2",
  quiz_result: "#ca8a04",
  referral_input: "#d97706",
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
  const labels = { message: "Сообщение", document: "Файл", input: "Ввод данных", condition: "Подписка", delay: "Пауза", video: "Видео", video_note: "Кружок", quiz_result: "Результат теста", referral_input: "Контакт знакомого" };
  return node ? node.type_label : labels[type] ?? type;
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
    label: wrapLabel(n.label.replace(/^Ветка \d+:\s*/, ""), 28),
    title: escapeHtml(n.label),
    shape: "box",
    widthConstraint: { minimum: 225, maximum: 225 },
    heightConstraint: { minimum: 66 },
    color: {
      background: n.boundary ? "#eff6ff" : "#ffffff",
      border: n.is_start ? "#16a34a" : TYPE_COLORS[n.type] ?? "#6b7280",
    },
    borderWidth: n.is_start ? 3 : 2,
    shapeProperties: { borderRadius: 10, borderDashes: n.boundary },
    font: { size: 14, color: "#1f2937", multi: false, vadjust: 0 },
    margin: 16,
    ...(savedPositions?.[n.id] ?? {}),
  }));
}

export function edgeDataset(graphData, positions = {}) {
  return graphData.edges.flatMap((e, index) => {
    const points = Object.keys(positions)
      .filter((id) => id.startsWith(`__route_${index}_`))
      .sort((a, b) => positions[a].x - positions[b].x);
    const path = [e.from, ...points, e.to];
    return path.slice(1).map((target, segment) => ({
    id: `edge_${index}_${segment}`,
    sourceNode: e.from,
    targetNode: e.to,
    from: path[segment],
    to: target,
    label: segment > 0 || e.label === "автоматически" ? "" : wrapLabel(e.label ?? "", 24),
    arrows: segment === path.length - 2 ? "to" : "",
    font: { size: 10, color: "#6b7280", strokeWidth: 8, strokeColor: "#ffffff", align: "top" },
    width: 1.5,
    color: { color: "#94a3b8", highlight: "#2563eb", hover: "#2563eb" },
    smooth: { enabled: true, type: "cubicBezier", forceDirection: "horizontal", roundness: 0.35 },
    }));
  });
}

export function routingNodes(positions) {
  return Object.entries(positions).filter(([id]) => id.startsWith("__route_")).map(([id, position]) => ({
    id, ...position, label: "", shape: "dot", size: 0.1,
    borderWidth: 0, color: "rgba(0,0,0,0)", chosen: false,
  }));
}

export function renderDetail(network, graphData, nodeId, onNavigate) {
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
                      ${b.next ? `<button class="graph-jump text-blue-600 hover:underline text-xs break-words text-right" data-target="${escapeHtml(b.next)}">→ ${escapeHtml(labelOf(b.next))}</button>` : '<span class="text-xs text-gray-400">Внешняя ссылка / согласие</span>'}
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
      if (onNavigate) {
        onNavigate(targetId);
        return;
      }
      network.selectNodes([targetId]);
      network.focus(targetId, { scale: 1, animation: { duration: 400, easingFunction: "easeInOutQuad" } });
      renderDetail(network, graphData, targetId);
    });
  });
}
