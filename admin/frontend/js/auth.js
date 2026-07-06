const originalFetch = window.fetch;
window.fetch = async (...args) => {
  const res = await originalFetch(...args);
  if (res.status === 401 && !args[0].toString().includes("/api/auth/")) {
    window.location.href = "/login.html";
  }
  return res;
};

export async function requireLogin() {
  try {
    const res = await fetch("/api/auth/me");
    if (!res.ok) throw new Error("not authenticated");
    const data = await res.json();
    document.getElementById("currentUsername").textContent = data.username;
    return true;
  } catch {
    window.location.href = "/login.html";
    return false;
  }
}

document.getElementById("logoutBtn").addEventListener("click", async () => {
  await fetch("/api/auth/logout", { method: "POST" });
  window.location.href = "/login.html";
});
