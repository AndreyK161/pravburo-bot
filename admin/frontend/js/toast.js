const DISPLAY_MS = 3000;
const FADE_MS = 400;

function getContainer() {
  let el = document.getElementById("toast-container");
  if (!el) {
    el = document.createElement("div");
    el.id = "toast-container";
    el.className = "fixed bottom-4 left-1/2 -translate-x-1/2 flex flex-col gap-2 z-50";
    document.body.appendChild(el);
  }
  return el;
}

export function showToast(message, type = "error") {
  const container = getContainer();
  const colors = type === "error" ? "bg-red-600" : "bg-green-600";

  const toast = document.createElement("div");
  toast.textContent = message;
  toast.className = `px-4 py-2 rounded-md shadow-lg text-sm text-white ${colors} transition-all ease-out opacity-0 translate-y-2`;
  toast.style.transitionDuration = `${FADE_MS}ms`;
  container.appendChild(toast);

  // Двойной rAF нужен, чтобы браузер точно успел отрисовать начальное
  // состояние (opacity-0) до снятия класса — иначе transition не запускается.
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      toast.classList.remove("opacity-0", "translate-y-2");
    });
  });

  setTimeout(() => {
    toast.classList.add("opacity-0", "translate-y-2");
    setTimeout(() => toast.remove(), FADE_MS);
  }, DISPLAY_MS);
}
