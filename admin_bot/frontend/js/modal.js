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

const linkOverlay = document.getElementById("linkModalOverlay");
const linkForm = document.getElementById("linkModalForm");
const linkUrlInput = document.getElementById("linkModalUrl");
const linkLabelWrap = document.getElementById("linkModalLabelWrap");
const linkLabelInput = document.getElementById("linkModalLabel");
const linkCancelBtn = document.getElementById("linkModalCancel");

// showLabelField=false — вставка ссылки поверх уже выделенного текста,
// тогда текстом ссылки остаётся само выделение и поле с текстом не нужно.
export function linkModal(defaultUrl = "", showLabelField = true) {
  return new Promise((resolve) => {
    linkUrlInput.value = defaultUrl;
    linkLabelInput.value = defaultUrl;
    linkLabelWrap.classList.toggle("hidden", !showLabelField);

    function cleanup(result) {
      linkOverlay.classList.add("opacity-0");
      linkForm.classList.add("opacity-0", "scale-95");
      setTimeout(() => linkOverlay.classList.add("hidden"), 200);
      linkForm.removeEventListener("submit", onSubmit);
      linkCancelBtn.removeEventListener("click", onCancel);
      linkOverlay.removeEventListener("click", onOverlayClick);
      resolve(result);
    }

    function onSubmit(e) {
      e.preventDefault();
      const url = linkUrlInput.value.trim();
      if (!url) return;
      const label = showLabelField ? linkLabelInput.value.trim() || url : null;
      cleanup({ url, label });
    }

    function onCancel() {
      cleanup(null);
    }

    function onOverlayClick(e) {
      if (e.target === linkOverlay) cleanup(null);
    }

    linkForm.addEventListener("submit", onSubmit);
    linkCancelBtn.addEventListener("click", onCancel);
    linkOverlay.addEventListener("click", onOverlayClick);

    linkOverlay.classList.remove("hidden");
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        linkOverlay.classList.remove("opacity-0");
        linkForm.classList.remove("opacity-0", "scale-95");
        linkUrlInput.focus();
        linkUrlInput.select();
      });
    });
  });
}
