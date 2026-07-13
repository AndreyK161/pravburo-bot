// vis-network по умолчанию трактует любой скролл как зум. Обсидиан-подобное
// поведение: свайп двумя пальцами двигает камеру, зумит только пинч (трекпад
// присылает такие события с ctrlKey=true) или Ctrl/Cmd + колесо мыши.
export function setupTrackpadPanning(network, container) {
  container.addEventListener(
    "wheel",
    (e) => {
      if (e.ctrlKey) return;
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
