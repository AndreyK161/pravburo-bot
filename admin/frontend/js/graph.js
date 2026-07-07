import { escapeHtml } from "./utils.js";
import { showToast } from "./toast.js";

const TYPE_COLORS = {
  message: "#2563eb",
  document: "#7c3aed",
  input: "#d97706",
  condition: "#dc2626",
  delay: "#6b7280",
};

let network = null;
let graphData = null;

async function fetchSavedPositions(nodeIds) {
  try {
    const res = await fetch("/api/scenario-graph/positions");
    if (!res.ok) throw new Error("Failed to fetch graph positions");
    const saved = await res.json();
    // Если список блоков сценария поменялся (добавили/удалили блок) — старые
    // координаты уже не описывают весь граф, лучше пересчитать раскладку заново.
    const savedIds = Object.keys(saved);
    const sameSet = savedIds.length === nodeIds.length && nodeIds.every((id) => id in saved);
    return sameSet ? saved : null;
  } catch {
    return null;
  }
}

async function savePositions(positions) {
  try {
    await fetch("/api/scenario-graph/positions", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(positions),
    });
  } catch {
    // Раскладку не удалось сохранить (сеть недоступна и т.п.) — не критично,
    // просто в следующий раз граф пересчитается заново.
  }
}

function renderLegend() {
  const legend = document.getElementById("scenarioGraphLegend");
  const typeItems = Object.entries(TYPE_COLORS)
    .map(
      ([type, color]) => `
      <span class="inline-flex items-center gap-1.5">
        <span class="inline-block w-2.5 h-2.5 rounded-full" style="background:${color}"></span>
        ${escapeHtml(typeLabelByType(type))}
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

function typeLabelByType(type) {
  const node = graphData?.nodes.find((n) => n.type === type);
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

function nodeDataset(savedPositions) {
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

function edgeDataset() {
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

function renderDetail(nodeId) {
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
      renderDetail(targetId);
    });
  });
}

export async function loadGraph() {
  if (network) return; // граф уже построен и живёт своей физикой — просто переключаемся на вкладку

  try {
    const res = await fetch("/api/scenario-graph");
    if (!res.ok) throw new Error("Failed to fetch scenario graph");
    graphData = await res.json();
  } catch {
    showToast("Не удалось загрузить граф сценария");
    return;
  }

  renderLegend();

  const nodeIds = graphData.nodes.map((n) => n.id);
  const savedPositions = await fetchSavedPositions(nodeIds);

  const container = document.getElementById("scenarioGraph");
  const data = { nodes: new vis.DataSet(nodeDataset(savedPositions)), edges: new vis.DataSet(edgeDataset()) };
  const options = {
    physics: {
      solver: "barnesHut",
      barnesHut: {
        gravitationalConstant: -4000,
        centralGravity: 0.15,
        springLength: 220,
        springConstant: 0.02,
        damping: 0.7,
        avoidOverlap: 1,
      },
      // Физика остаётся включённой постоянно (как в Obsidian): пока узлы стоят
      // на месте, она сама "засыпает" (см. minVelocity ниже) и не жрёт CPU, но
      // стоит потянуть один узел — соседи мягко, пружинисто на это реагируют.
      minVelocity: 0.75,
      adaptiveTimestep: true,
      // Если раскладка уже сохранена, узлы стартуют из финальных координат —
      // прогонять анимацию стабилизации заново не нужно, они и так на месте.
      stabilization: savedPositions ? false : { iterations: 250 },
    },
    interaction: { hover: true, tooltipDelay: 200, dragNodes: true, dragView: true },
    nodes: { shadow: false },
    edges: { shadow: false },
  };

  network = new vis.Network(container, data, options);

  const idleJiggle = setupIdleJiggle(network);

  // На сервере раскладка сохраняется один-единственный раз — когда граф в
  // первый раз вообще кто-то разложил с нуля (см. ниже). Перетаскивание узлов
  // после этого — чисто локальная, "для себя" история (чтобы удобнее было
  // разглядывать текст), она никуда не пишется: и сервер не дёргаем на каждое
  // перетаскивание, и общая для всех раскладка не расползается со временем.
  //
  // Важно: после отпускания узла (или окончания доезда по инерции) настоящая
  // физика ещё какое-то время сама доводит соседей до равновесия — момент
  // dragEnd/окончания доезда не значит, что движение уже реально прекратилось.
  // Если возобновить дыхание немедленно, оно возьмёт координаты "на лету" за
  // новую точку отсчёта, а физика в это же время продолжит их сама двигать —
  // два механизма толкают одни и те же узлы одновременно, отсюда и рывок.
  // Поэтому ждём небольшую паузу после последнего движения и только потом
  // fixируем текущие (уже реально осевшие) координаты и включаем дыхание снова.
  let interactionActive = false;
  let resumeTimer = null;
  const scheduleResume = () => {
    clearTimeout(resumeTimer);
    resumeTimer = setTimeout(() => {
      if (interactionActive) return; // успели начать новое перетаскивание — подождём его окончания
      idleJiggle?.setAnchors(network.getPositions());
      idleJiggle?.resume();
    }, 400);
  };
  if (savedPositions) {
    idleJiggle?.setAnchors(savedPositions);
  } else {
    network.once("stabilizationIterationsDone", () => {
      const positions = network.getPositions();
      idleJiggle?.setAnchors(positions);
      savePositions(positions);
    });
  }

  const fling = setupFling(network, () => {
    interactionActive = false;
    scheduleResume();
  });

  network.on("dragStart", () => {
    interactionActive = true;
    clearTimeout(resumeTimer);
    idleJiggle?.pause();
    fling.trackReset();
  });
  network.on("dragging", (params) => fling.trackSample(params.nodes[0]));
  network.on("dragEnd", (params) => {
    const nodeId = params.nodes[0];
    if (nodeId && fling.tryStart(nodeId)) return; // бросили резко — доиграет инерция, дальше сама вызовет resume
    interactionActive = false;
    scheduleResume();
  });

  network.on("click", (params) => {
    if (!params.nodes.length) return;
    const nodeId = params.nodes[0];
    renderDetail(nodeId);
    network.focus(nodeId, {
      scale: Math.max(network.getScale(), 1),
      animation: { duration: 400, easingFunction: "easeInOutQuad" },
    });
  });
  setupTrackpadPanning(network, container);
}

// Плавное торможение при отпускании: узел не "ставится" мгновенно там, где
// его бросили, а быстро, но плавно гасит инерцию за пару кадров — небольшой,
// еле заметный доезд вместо резкого щелчка на месте. Скорость жёстко зажата
// сверху, поэтому даже резкий взмах мышью не унесёт узел далеко.
function setupFling(network, onSettle) {
  const MAX_SPEED = 90; // мировых единиц/сек — потолок, выше уже не разгоняется
  const FRICTION_PER_SEC = 0.002; // тормозит быстро — доезд едва заметен
  const MAX_DURATION_MS = 220;
  const MIN_SPEED_TO_ANIMATE = 15; // совсем незаметное движение — просто ставим на место без анимации

  let samples = [];
  let rafId = null;

  return {
    trackReset() {
      samples = [];
      if (rafId !== null) {
        cancelAnimationFrame(rafId);
        rafId = null;
      }
    },
    trackSample(nodeId) {
      if (!nodeId) return;
      const pos = network.getPositions([nodeId])[nodeId];
      if (!pos) return;
      const now = performance.now();
      samples.push({ t: now, x: pos.x, y: pos.y });
      const cutoff = now - 100;
      while (samples.length > 2 && samples[0].t < cutoff) samples.shift();
    },
    // Возвращает true, если запустил доезд (дальше сам вызовет onSettle по завершении).
    tryStart(nodeId) {
      if (samples.length < 2) return false;
      const first = samples[0];
      const last = samples[samples.length - 1];
      const dt = (last.t - first.t) / 1000;
      samples = [];
      if (dt <= 0) return false;

      let vx = (last.x - first.x) / dt;
      let vy = (last.y - first.y) / dt;
      const speed = Math.hypot(vx, vy);
      if (speed < MIN_SPEED_TO_ANIMATE) return false;
      if (speed > MAX_SPEED) {
        // не меняем направление, просто срезаем модуль скорости до потолка
        vx = (vx / speed) * MAX_SPEED;
        vy = (vy / speed) * MAX_SPEED;
      }

      let x = last.x;
      let y = last.y;
      const startTime = performance.now();
      let prevTime = startTime;

      const step = (now) => {
        const frameDt = Math.min((now - prevTime) / 1000, 0.05);
        prevTime = now;
        x += vx * frameDt;
        y += vy * frameDt;
        const decay = Math.pow(FRICTION_PER_SEC, frameDt);
        vx *= decay;
        vy *= decay;
        network.moveNode(nodeId, x, y);

        if (Math.hypot(vx, vy) < MIN_SPEED_TO_ANIMATE || now - startTime > MAX_DURATION_MS) {
          rafId = null;
          onSettle();
          return;
        }
        rafId = requestAnimationFrame(step);
      };
      rafId = requestAnimationFrame(step);
      return true;
    },
  };
}

// Лёгкое непрерывное "дыхание" узлов, как в Obsidian: каждый узел плавно
// гуляет по маленькому эллипсу вокруг своей "домашней" точки — синусоида
// считается на каждый кадр (requestAnimationFrame), поэтому движение гладкое,
// без скачков, в отличие от резких дискретных смещений раз в N миллисекунд.
// Физику это не трогает вообще — только визуально сдвигает точки, поэтому не
// мешает настоящей физике при реальном перетаскивании и не расшатывает общую
// сохранённую раскладку. На мобилке отключаем — лишний расход батареи.
function setupIdleJiggle(network) {
  if (window.matchMedia("(max-width: 767px)").matches) return null;

  const AMPLITUDE_PX = 6;
  let anchors = {};
  let params = {};
  let paused = false;
  let rafId = null;

  function tick(timeMs) {
    if (!paused) {
      // network.moveNode — лёгкий способ просто переставить точку на канвасе,
      // в отличие от nodesDataSet.update() он не гоняет пересчёт лейблов/размеров
      // узла на каждый кадр, поэтому и не подтормаживает на 40+ узлах.
      for (const id of Object.keys(anchors)) {
        const { startMs, speed, angle } = params[id];
        // Считаем от момента, когда узел зафиксировали (setAnchors), а не от
        // абсолютного времени страницы — при elapsed=0 sin(0)=0, то есть
        // смещение всегда стартует ровно с нуля (с точки, где узел реально
        // остановился) и плавно нарастает, а не прыгает на случайную величину.
        const elapsed = (timeMs - startMs) / 1000;
        const magnitude = Math.sin(elapsed * speed) * AMPLITUDE_PX;
        network.moveNode(id, anchors[id].x + magnitude * Math.cos(angle), anchors[id].y + magnitude * Math.sin(angle));
      }
    }
    rafId = requestAnimationFrame(tick);
  }
  rafId = requestAnimationFrame(tick);

  return {
    setAnchors(positions) {
      anchors = positions;
      params = {};
      const now = performance.now();
      for (const id of Object.keys(positions)) {
        // Разная скорость и направление на узел — иначе все дышали бы синхронно, как строем.
        params[id] = { startMs: now, speed: 0.4 + Math.random() * 0.3, angle: Math.random() * Math.PI * 2 };
      }
    },
    pause() {
      paused = true;
    },
    resume() {
      paused = false;
    },
    stop() {
      if (rafId !== null) cancelAnimationFrame(rafId);
    },
  };
}

// По умолчанию vis-network любой скролл (в т.ч. двухпальцевый свайп на трекпаде)
// трактует как зум. Обсидиан-подобное поведение: свайп двумя пальцами двигает
// камеру, а зумит только пинч (тачпад присылает такие события с ctrlKey=true)
// или зажатый Ctrl/Cmd + скролл колесом мыши.
function setupTrackpadPanning(network, container) {
  container.addEventListener(
    "wheel",
    (e) => {
      if (e.ctrlKey) return; // пинч-зум — пусть обработает сам vis-network
      e.preventDefault();
      e.stopPropagation();
      const scale = network.getScale();
      const position = network.getViewPosition();
      network.moveTo({
        position: {
          x: position.x + e.deltaX / scale,
          y: position.y + e.deltaY / scale,
        },
        scale,
        animation: false,
      });
    },
    { capture: true, passive: false }
  );
}
