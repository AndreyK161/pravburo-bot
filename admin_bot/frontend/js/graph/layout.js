export const GRAPH_SECTIONS = [
  { id: "entry", label: "Начало" },
  { id: "hard", label: "1 · Плачу вовремя" },
  { id: "collectors", label: "2 · Коллекторы" },
  { id: "bailiffs", label: "3 · Приставы" },
  { id: "consultation", label: "Консультация" },
  { id: "referral", label: "Реферальная программа" },
];

export function sectionOf(node) {
  const id = node.id;
  if (/^advertising_/.test(id)) return "entry";
  if (/^(hard_|quiz_|situation_hard$)/.test(id)) return "hard";
  if (/^(collectors_|situation_collectors$)/.test(id)) return "collectors";
  if (/^(bailiffs_|situation_bailiffs$)/.test(id)) return "bailiffs";
  if (/^consultation/.test(id)) return "consultation";
  if (/^referral/.test(id)) return "referral";
  return "entry";
}

export function sectionGraph(graph, section) {
  const ownIds = new Set(graph.nodes.filter((n) => sectionOf(n) === section).map((n) => n.id));
  const visibleIds = new Set(ownIds);
  for (const edge of graph.edges) {
    if (ownIds.has(edge.from)) visibleIds.add(edge.to);
  }
  return {
    ...graph,
    nodes: graph.nodes.filter((n) => visibleIds.has(n.id)).map((n) => ({ ...n, boundary: !ownIds.has(n.id) })),
    edges: graph.edges.filter((e) => ownIds.has(e.from) && visibleIds.has(e.to)),
  };
}

export function layoutPositions(graph) {
  const adjacency = new Map(graph.nodes.map((n) => [n.id, []]));
  for (const edge of graph.edges) adjacency.get(edge.from)?.push(edge.to);
  // Убираем только обратные связи из расчёта уровней. На схеме они остаются.
  const state = new Map();
  const order = [];
  const forward = new Map(graph.nodes.map((n) => [n.id, []]));
  function visit(id) {
    state.set(id, "visiting");
    for (const target of adjacency.get(id) ?? []) {
      if (state.get(target) === "visiting") continue;
      forward.get(id).push(target);
      if (!state.has(target)) visit(target);
    }
    state.set(id, "done");
    order.push(id);
  }
  for (const node of graph.nodes) if (!state.has(node.id)) visit(node.id);
  const levels = new Map(graph.nodes.map((n) => [n.id, 0]));
  for (const id of order.reverse()) {
    for (const target of forward.get(id)) {
      levels.set(target, Math.max(levels.get(target), levels.get(id) + 1));
    }
  }
  return arrangeLayers(graph, levels);
}

function arrangeLayers(graph, levels) {
  const layers = [];
  const parents = new Map();
  const children = new Map();
  function add(id, level) {
    (layers[level] ??= []).push(id);
    parents.set(id, []);
    children.set(id, []);
  }
  for (const node of graph.nodes) add(node.id, levels.get(node.id));
  function link(from, to) {
    children.get(from).push(to);
    parents.get(to).push(from);
  }
  // Длинным стрелкам резервируем проходы между карточками на каждом уровне.
  for (const [index, edge] of graph.edges.entries()) {
    const first = levels.get(edge.from);
    const last = levels.get(edge.to);
    if (last <= first) continue;
    let previous = edge.from;
    for (let level = first + 1; level < last; level++) {
      const id = `__route_${index}_${level}`;
      add(id, level);
      link(previous, id);
      previous = id;
    }
    link(previous, edge.to);
  }
  const rows = new Map();
  function updateRows() {
    for (const layer of layers) {
      layer.forEach((id, row) => rows.set(id, row - (layer.length - 1) / 2));
    }
  }
  function crossings() {
    let count = 0;
    for (const layer of layers) {
      for (let i = 0; i < layer.length; i++) {
        for (let j = i + 1; j < layer.length; j++) {
          for (const left of children.get(layer[i])) {
            for (const right of children.get(layer[j])) {
              if (rows.get(left) > rows.get(right)) count++;
            }
          }
        }
      }
    }
    return count;
  }
  updateRows();
  let best = layers.map((layer) => [...layer]);
  let bestCount = crossings();
  // Чередуем проходы от родителей к детям и обратно, выбирая порядок
  // по центру соседей. Сохраняем только раскладку с меньшим числом пересечений.
  for (let pass = 0; pass < 16; pass++) {
    const downward = pass % 2 === 0;
    const indices = layers.map((_, index) => index);
    if (!downward) indices.reverse();
    const neighbors = downward ? parents : children;
    for (const index of indices) {
      const center = (id) => {
        const adjacent = neighbors.get(id);
        return adjacent.length
          ? adjacent.reduce((sum, next) => sum + rows.get(next), 0) / adjacent.length
          : rows.get(id);
      };
      layers[index].sort((a, b) => center(a) - center(b));
      updateRows();
    }
    const count = crossings();
    if (count < bestCount) {
      bestCount = count;
      best = layers.map((layer) => [...layer]);
    }
  }
  const positions = {};
  best.forEach((layer, level) => {
    layer.forEach((id, row) => {
      positions[id] = { x: level * 400, y: (row - (layer.length - 1) / 2) * 200 };
    });
  });
  return positions;
}
