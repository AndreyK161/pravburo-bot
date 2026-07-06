export const CHART_COLORS = ["#1f2937", "#2563eb", "#16a34a", "#d97706", "#dc2626", "#7c3aed", "#0891b2", "#db2777"];

export function colorForIndex(i) {
  return CHART_COLORS[i % CHART_COLORS.length];
}

export function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
