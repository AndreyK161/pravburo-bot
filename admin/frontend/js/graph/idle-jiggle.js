// Лёгкое непрерывное покачивание узлов вокруг их "домашних" точек — как в
// Obsidian. Использует network.moveNode (лёгкий, без пересчёта лейблов),
// физику не трогает вообще, поэтому не мешает реальному перетаскиванию.
export function setupIdleJiggle(network) {
  if (window.matchMedia("(max-width: 767px)").matches) return null;

  const AMPLITUDE_PX = 6;
  let anchors = {};
  let params = {};
  // Два независимых тормоза: реальное перетаскивание (dragPaused) и вкладка
  // графа вообще не видна (tabVisible=false) — во втором случае rAF не
  // запускается вовсе, а не крутится вхолостую.
  let dragPaused = false;
  let tabVisible = true;
  let rafId = null;

  function tick(timeMs) {
    for (const id of Object.keys(anchors)) {
      const { startMs, speed, angle } = params[id];
      // Считаем от момента setAnchors, а не от абсолютного времени страницы:
      // при elapsed=0 sin(0)=0, смещение стартует с нуля и плавно растёт,
      // а не прыгает на случайную величину при каждом возобновлении.
      const elapsed = (timeMs - startMs) / 1000;
      const magnitude = Math.sin(elapsed * speed) * AMPLITUDE_PX;
      network.moveNode(id, anchors[id].x + magnitude * Math.cos(angle), anchors[id].y + magnitude * Math.sin(angle));
    }
    rafId = requestAnimationFrame(tick);
  }

  function syncRunning() {
    const shouldRun = !dragPaused && tabVisible;
    if (shouldRun && rafId === null) {
      rafId = requestAnimationFrame(tick);
    } else if (!shouldRun && rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  }
  syncRunning();

  return {
    setAnchors(positions) {
      anchors = positions;
      params = {};
      const now = performance.now();
      for (const id of Object.keys(positions)) {
        params[id] = { startMs: now, speed: 0.4 + Math.random() * 0.3, angle: Math.random() * Math.PI * 2 };
      }
    },
    pause() {
      dragPaused = true;
      syncRunning();
    },
    resume() {
      dragPaused = false;
      syncRunning();
    },
    setTabVisible(visible) {
      tabVisible = visible;
      syncRunning();
    },
    stop() {
      if (rafId !== null) cancelAnimationFrame(rafId);
      rafId = null;
    },
  };
}
