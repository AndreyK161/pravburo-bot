import { showToast } from "../toast.js";
import { fetchSavedPositions, savePositions } from "./api.js";
import { renderLegend, nodeDataset, edgeDataset, renderDetail } from "./render.js";
import { setupIdleJiggle } from "./idle-jiggle.js";
import { setupFling } from "./fling.js";
import { setupTrackpadPanning } from "./trackpad-panning.js";

let network = null;
let idleJiggle = null;
let graphTabVisible = false;

export function setGraphTabVisible(visible) {
  graphTabVisible = visible;
  idleJiggle?.setTabVisible(visible);
}

// Плюс сворачивание/переключение вкладки браузера — requestAnimationFrame и
// так сам притормаживает в фоне, но на всякий случай.
document.addEventListener("visibilitychange", () => {
  idleJiggle?.setTabVisible(graphTabVisible && !document.hidden);
});

export async function loadGraph() {
  if (network) return; // граф уже построен и живёт своей физикой

  let graphData;
  try {
    const res = await fetch("/api/scenario-graph");
    if (!res.ok) throw new Error("Failed to fetch scenario graph");
    graphData = await res.json();
  } catch {
    showToast("Не удалось загрузить граф сценария");
    return;
  }

  renderLegend(graphData);

  const nodeIds = graphData.nodes.map((n) => n.id);
  const savedPositions = await fetchSavedPositions(nodeIds);

  const container = document.getElementById("scenarioGraph");
  const data = {
    nodes: new vis.DataSet(nodeDataset(graphData, savedPositions)),
    edges: new vis.DataSet(edgeDataset(graphData)),
  };
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
      // Физика включена постоянно (как в Obsidian): без движения она сама
      // "засыпает" (minVelocity) и не жрёт CPU, но при перетаскивании соседи
      // мягко, пружинисто реагируют.
      minVelocity: 0.75,
      adaptiveTimestep: true,
      stabilization: savedPositions ? false : { iterations: 250 },
    },
    interaction: { hover: true, tooltipDelay: 200, dragNodes: true, dragView: true },
    nodes: { shadow: false },
    edges: { shadow: false },
  };

  network = new vis.Network(container, data, options);

  graphTabVisible = true;
  idleJiggle = setupIdleJiggle(network);

  // Раскладка сохраняется на сервере один раз — при первом построении графа
  // с нуля. Дальнейшее перетаскивание узлов — локальное, никуда не пишется
  // (не гоняем сервер зря и не расшатываем общую для всех раскладку).
  //
  // После отпускания/доезда физика ещё немного сама доводит соседей до
  // равновесия — возобновлять дыхание раньше нельзя, оба механизма толкали бы
  // одни и те же узлы одновременно. Поэтому ждём небольшую паузу.
  let interactionActive = false;
  let resumeTimer = null;
  const scheduleResume = () => {
    clearTimeout(resumeTimer);
    resumeTimer = setTimeout(() => {
      if (interactionActive) return;
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
    if (nodeId && fling.tryStart(nodeId)) return; // бросили резко — доиграет сама, дальше вызовет resume
    interactionActive = false;
    scheduleResume();
  });

  network.on("click", (params) => {
    if (!params.nodes.length) return;
    const nodeId = params.nodes[0];
    renderDetail(network, graphData, nodeId);
    network.focus(nodeId, {
      scale: Math.max(network.getScale(), 1),
      animation: { duration: 400, easingFunction: "easeInOutQuad" },
    });
  });

  setupTrackpadPanning(network, container);
}
