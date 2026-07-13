export async function fetchSavedPositions(nodeIds) {
  try {
    const res = await fetch("/api/scenario-graph/positions");
    if (!res.ok) throw new Error("Failed to fetch graph positions");
    const saved = await res.json();
    // Набор блоков поменялся — старые координаты не описывают весь граф.
    const savedIds = Object.keys(saved);
    const sameSet = savedIds.length === nodeIds.length && nodeIds.every((id) => id in saved);
    return sameSet ? saved : null;
  } catch {
    return null;
  }
}

export async function savePositions(positions) {
  try {
    await fetch("/api/scenario-graph/positions", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(positions),
    });
  } catch {
    // не критично — просто пересчитается заново в следующий раз
  }
}
