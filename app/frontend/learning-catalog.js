async function loadLearningCatalog() {
  const response = await fetch("learning-catalog.json", { cache: "no-cache" });
  if (!response.ok) throw new Error(`Learning catalog request failed (${response.status})`);
  return response.json();
}

function lessonModesHash(category) {
  return category === "drugs" ? "#drugs" : `#topics/${encodeURIComponent(category)}`;
}

function lessonPageUrl(category, mode, topic) {
  const params = new URLSearchParams();
  if (category !== "drugs") params.set("category", category);
  if (topic) params.set(category === "drugs" ? "drug" : "topic", topic);
  return `${mode === "game" ? "game" : "focused"}.html${params.size ? "?" + params : ""}`;
}
