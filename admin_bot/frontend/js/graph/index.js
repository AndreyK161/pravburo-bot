import { showToast } from "../toast.js";
import { renderLegend, nodeDataset, edgeDataset, renderDetail, routingNodes } from "./render.js";
import { setupTrackpadPanning } from "./trackpad-panning.js";
import { GRAPH_SECTIONS, sectionOf, sectionGraph, layoutPositions } from "./layout.js";
import {
  getScenarioPlatform,
  loadScenarioPlatforms,
  onScenarioPlatformChange,
  renderPlatformSwitcher,
} from "../scenario-platform.js";

let network = null;
let graphData = null;
let currentSection = "entry";
let loadedPlatform = null;
let platformsInitialized = false;
let removePanning = null;
let edges = null;
const sectionPositions = new Map();

export function setGraphTabVisible(visible) {
  if (visible) network?.redraw();
}

function navigateTo(nodeId) {
  const node = graphData.nodes.find((n) => n.id === nodeId);
  if (!node) return;
  const section = sectionOf(node);
  if (section !== currentSection) drawSection(section);
  network.selectNodes([nodeId]);
  network.selectEdges(edges.get().filter((edge) => edge.sourceNode === nodeId || edge.targetNode === nodeId).map((edge) => edge.id));
  network.focus(nodeId, { scale: 0.9, animation: { duration: 250 } });
  renderDetail(network, graphData, nodeId, navigateTo);
}

function drawSection(section, reset = false) {
  if (network) {
    sectionPositions.set(currentSection, network.getPositions());
    removePanning?.();
    network.destroy();
  }
  currentSection = section;
  if (reset) sectionPositions.delete(section);
  const visible = sectionGraph(graphData, section);
  const positions = sectionPositions.get(section) ?? layoutPositions(visible);
  const container = document.getElementById("scenarioGraph");
  edges = new vis.DataSet(edgeDataset(visible, positions));
  network = new vis.Network(container, {
    nodes: new vis.DataSet([...nodeDataset(visible, positions), ...routingNodes(positions)]),
    edges,
  }, {
    physics: false,
    layout: { improvedLayout: false },
    interaction: { hover: true, tooltipDelay: 250, dragNodes: true, dragView: true },
    nodes: { shadow: false },
    edges: { shadow: false, selectionWidth: 2 },
  });
  renderLegend(visible);
  document.getElementById("graphDetailContent").classList.add("hidden");
  document.getElementById("graphDetailEmpty").classList.remove("hidden");
  document.querySelectorAll("[data-graph-section]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.graphSection === section);
    button.setAttribute("aria-pressed", String(button.dataset.graphSection === section));
  });
  document.getElementById("graphSectionHint").textContent =
    "Сценарий идёт слева направо. Прокрутка перемещает схему, Ctrl + прокрутка меняет масштаб. Пунктирная карточка открывает другой раздел.";
  const first = visible.nodes.find((n) => n.is_start) ?? visible.nodes.find((n) => !n.boundary);
  network.once("afterDrawing", () => {
    if (visible.nodes.length <= 10) {
      network.fit({ maxZoomLevel: 0.9, animation: false });
    } else if (first) {
      network.moveTo({ position: { x: positions[first.id].x + 230, y: positions[first.id].y + 100 }, scale: 0.85 });
    }
  });
  network.on("click", ({ nodes }) => {
    if (nodes.length) navigateTo(nodes[0]);
  });
  removePanning = setupTrackpadPanning(network, container);
}

export async function loadGraph() {
  if (!platformsInitialized) {
    platformsInitialized = true;
    await loadScenarioPlatforms();
    renderPlatformSwitcher(document.getElementById("graphPlatformSwitcher"));
    onScenarioPlatformChange(() => loadGraph());
    document.getElementById("graphFit").onclick = () => network?.fit({ maxZoomLevel: 1, animation: true });
    document.getElementById("graphReset").onclick = () => drawSection(currentSection, true);
    document.getElementById("graphZoomIn").onclick = () => network?.moveTo({ scale: Math.min(1.8, network.getScale() * 1.25) });
    document.getElementById("graphZoomOut").onclick = () => network?.moveTo({ scale: Math.max(0.08, network.getScale() / 1.25) });
  }
  const platform = getScenarioPlatform();
  if (network && loadedPlatform === platform) return;
  try {
    const response = await fetch(`/api/scenario-graph?platform=${encodeURIComponent(platform)}`);
    if (!response.ok) throw new Error("Failed to fetch scenario graph");
    graphData = await response.json();
  } catch {
    showToast("Не удалось загрузить граф сценария");
    return;
  }
  sectionPositions.clear();
  const sections = document.getElementById("graphSections");
  sections.replaceChildren();
  for (const section of GRAPH_SECTIONS) {
    if (!graphData.nodes.some((n) => sectionOf(n) === section.id)) continue;
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.graphSection = section.id;
    button.textContent = section.label;
    button.onclick = () => drawSection(section.id);
    sections.append(button);
  }
  loadedPlatform = platform;
  drawSection("entry");
}
