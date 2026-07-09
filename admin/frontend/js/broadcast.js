import { escapeHtml } from "./utils.js";
import { fetchTags } from "./tags.js";
import { showToast } from "./toast.js";
import { confirmModal, linkModal } from "./modal.js";

export async function loadBroadcastTags() {
  let tags;
  try {
    tags = await fetchTags();
  } catch {
    showToast("Не удалось загрузить теги");
    return;
  }
  const select = document.getElementById("broadcastTag");
  select.innerHTML = ['<option value="">Всем пользователям</option>']
    .concat(tags.map((t) => `<option value="${t.id}">Тег: ${escapeHtml(t.name)}</option>`))
    .join("");
}

const editor = document.getElementById("broadcastText");

document.getElementById("broadcastBoldBtn").addEventListener("click", () => {
  editor.focus();
  document.execCommand("bold");
});
document.getElementById("broadcastItalicBtn").addEventListener("click", () => {
  editor.focus();
  document.execCommand("italic");
});
document.getElementById("broadcastUnderlineBtn").addEventListener("click", () => {
  editor.focus();
  document.execCommand("underline");
});
document.getElementById("broadcastStrikeBtn").addEventListener("click", () => {
  editor.focus();
  document.execCommand("strikeThrough");
});

document.getElementById("broadcastLinkBtn").addEventListener("click", async () => {
  const activeSelection = window.getSelection();
  const hasRangeInEditor = activeSelection && activeSelection.rangeCount > 0 && editor.contains(activeSelection.anchorNode);
  const savedRange = hasRangeInEditor ? activeSelection.getRangeAt(0).cloneRange() : null;
  const hasTextSelection = !!savedRange && !savedRange.collapsed;

  const result = await linkModal("", !hasTextSelection);
  if (!result) return;
  const href = /^[a-z][a-z0-9+.-]*:/i.test(result.url) ? result.url : `https://${result.url}`;

  editor.focus();
  const selection = window.getSelection();
  selection.removeAllRanges();
  if (savedRange) {
    selection.addRange(savedRange);
  } else {
    const range = document.createRange();
    range.selectNodeContents(editor);
    range.collapse(false);
    selection.addRange(range);
  }

  if (hasTextSelection) {
    document.execCommand("createLink", false, href);
  } else {
    document.execCommand("insertHTML", false, `<a href="${href.replace(/"/g, "&quot;")}">${escapeHtml(result.label)}</a>`);
  }
});

const DANGEROUS_TAGS = new Set(["SCRIPT", "STYLE", "IFRAME", "OBJECT", "EMBED", "LINK", "META", "IMG", "SVG"]);

function isSafeUrl(value) {
  return !/^\s*javascript:/i.test(value);
}

function sanitizeHtmlForPaste(html) {
  const template = document.createElement("template");
  template.innerHTML = html;

  const walker = document.createTreeWalker(template.content, NodeFilter.SHOW_ELEMENT);
  const toRemove = [];
  let node = walker.nextNode();
  while (node) {
    if (DANGEROUS_TAGS.has(node.tagName)) {
      toRemove.push(node);
    } else {
      Array.from(node.attributes).forEach((attr) => {
        const isSafeHref = node.tagName === "A" && attr.name === "href" && isSafeUrl(attr.value);
        if (!isSafeHref) node.removeAttribute(attr.name);
      });
    }
    node = walker.nextNode();
  }
  toRemove.forEach((el) => el.remove());

  return template.innerHTML;
}

editor.addEventListener("paste", (e) => {
  e.preventDefault();
  const html = e.clipboardData.getData("text/html");
  if (html) {
    document.execCommand("insertHTML", false, sanitizeHtmlForPaste(html));
  } else {
    document.execCommand("insertText", false, e.clipboardData.getData("text/plain"));
  }
});

// DOM редактора -> текст с HTML-тегами, которые понимает Telegram
// (parse_mode="HTML"). Что не входит в TAG_MAP — просто разворачиваем,
// оставляя только текстовое содержимое, без обёртки.
const TAG_MAP = { B: "b", STRONG: "b", I: "i", EM: "i", U: "u", S: "s", STRIKE: "s", DEL: "s", CODE: "code", PRE: "pre" };

function escapeForTelegram(text) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function serializeNode(node) {
  if (node.nodeType === Node.TEXT_NODE) return escapeForTelegram(node.textContent);
  if (node.nodeType !== Node.ELEMENT_NODE) return "";
  if (node.tagName === "BR") return "\n";

  const inner = Array.from(node.childNodes).map(serializeNode).join("");

  if (node.tagName === "A") {
    const href = node.getAttribute("href");
    return href && isSafeUrl(href) ? `<a href="${escapeForTelegram(href)}">${inner}</a>` : inner;
  }

  const tag = TAG_MAP[node.tagName];
  if (tag) return `<${tag}>${inner}</${tag}>`;

  // div/p из переносов строк в contenteditable — просто перевод строки после содержимого.
  return ["DIV", "P"].includes(node.tagName) ? `${inner}\n` : inner;
}

function editorToTelegramHtml() {
  return Array.from(editor.childNodes)
    .map(serializeNode)
    .join("")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

const broadcastImageInput = document.getElementById("broadcastImage");
const broadcastImagePreview = document.getElementById("broadcastImagePreview");
broadcastImageInput.addEventListener("change", () => {
  const file = broadcastImageInput.files[0];
  if (!file) {
    broadcastImagePreview.classList.add("hidden");
    broadcastImagePreview.src = "";
    return;
  }
  broadcastImagePreview.src = URL.createObjectURL(file);
  broadcastImagePreview.classList.remove("hidden");
});

document.getElementById("broadcastSendBtn").addEventListener("click", async () => {
  const text = editorToTelegramHtml();
  const tagId = document.getElementById("broadcastTag").value;
  const imageFile = broadcastImageInput.files[0] ?? null;
  const resultEl = document.getElementById("broadcastResult");

  if (!text) {
    resultEl.textContent = "Введите текст сообщения";
    resultEl.className = "text-sm text-red-600";
    return;
  }

  const targetLabel = tagId
    ? document.getElementById("broadcastTag").selectedOptions[0].textContent
    : "всем пользователям";
  const confirmed = await confirmModal(
    `Отправить рассылку ${targetLabel}?\n\nЭто действие необратимо.`,
    "Отправить"
  );
  if (!confirmed) return;

  const btn = document.getElementById("broadcastSendBtn");
  btn.disabled = true;
  btn.textContent = "Отправка...";
  resultEl.textContent = "";

  const formData = new FormData();
  formData.append("text", text);
  if (tagId) formData.append("tag_id", tagId);
  if (imageFile) formData.append("image", imageFile);

  try {
    const res = await fetch("/api/broadcast", { method: "POST", body: formData });
    const data = await res.json();
    if (res.ok) {
      resultEl.className = "text-sm text-gray-700";
      resultEl.textContent = `Готово: доставлено ${data.sent} из ${data.total}, заблокировали бота ${data.blocked}, ошибок ${data.failed}.`;
      editor.innerHTML = "";
      broadcastImageInput.value = "";
      broadcastImagePreview.classList.add("hidden");
      broadcastImagePreview.src = "";
    } else {
      resultEl.className = "text-sm text-red-600";
      resultEl.textContent = data.detail ?? "Не удалось отправить рассылку";
    }
  } catch {
    showToast("Не удалось отправить рассылку: ошибка сети");
  } finally {
    btn.disabled = false;
    btn.textContent = "Отправить рассылку";
  }
});
