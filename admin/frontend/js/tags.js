export async function fetchTags() {
  const res = await fetch("/api/tags");
  if (!res.ok) throw new Error("Failed to fetch tags");
  return res.json();
}

export async function createTag(name) {
  return fetch("/api/tags", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}
