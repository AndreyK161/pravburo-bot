const overlay = document.getElementById("confirmModalOverlay");
const box = document.getElementById("confirmModalBox");
const messageEl = document.getElementById("confirmModalMessage");
const cancelBtn = document.getElementById("confirmModalCancel");
const confirmBtn = document.getElementById("confirmModalConfirm");

export function confirmModal(message, confirmLabel = "Подтвердить") {
  return new Promise((resolve) => {
    messageEl.textContent = message;
    confirmBtn.textContent = confirmLabel;

    function cleanup(result) {
      overlay.classList.add("opacity-0");
      box.classList.add("opacity-0", "scale-95");
      setTimeout(() => overlay.classList.add("hidden"), 200);
      cancelBtn.removeEventListener("click", onCancel);
      confirmBtn.removeEventListener("click", onConfirm);
      overlay.removeEventListener("click", onOverlayClick);
      resolve(result);
    }

    function onCancel() {
      cleanup(false);
    }

    function onConfirm() {
      cleanup(true);
    }

    function onOverlayClick(e) {
      if (e.target === overlay) cleanup(false);
    }

    cancelBtn.addEventListener("click", onCancel);
    confirmBtn.addEventListener("click", onConfirm);
    overlay.addEventListener("click", onOverlayClick);

    overlay.classList.remove("hidden");
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        overlay.classList.remove("opacity-0");
        box.classList.remove("opacity-0", "scale-95");
      });
    });
  });
}
