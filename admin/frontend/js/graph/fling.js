// Плавное торможение при отпускании узла вместо мгновенной "постановки на
// место". Скорость жёстко зажата сверху — резкий взмах мышью не унесёт узел
// далеко (см. MAX_SPEED).
export function setupFling(network, onSettle) {
  const MAX_SPEED = 90;
  const FRICTION_PER_SEC = 0.002;
  const MAX_DURATION_MS = 220;
  const MIN_SPEED_TO_ANIMATE = 15;

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
    // true — если запустил доезд (дальше сам вызовет onSettle по завершении).
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
