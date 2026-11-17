// Shared controller for the Focused and Game lesson pages.
(function () {
  const params = new URLSearchParams(location.search);
  const categoryKey = params.get("category") || "drugs";
  const view = document.body.dataset.pathView;
  const otherView = view === "game" ? "focused" : "game";
  const select = document.getElementById("drugSelect");
  const switchLink = document.getElementById("switchLink");
  const map = document.getElementById("pathMap");

  function setLessonSource(source) {
    document.body.dataset.lessonSource = source;
    document.dispatchEvent(new Event("lesson-source-change"));
  }

  setLessonSource(categoryKey === "drugs" ? "drug" : "outline");

  function showStatus(text) {
    const status = document.createElement("div");
    status.className = "empty-state";
    status.setAttribute("role", "status");
    status.textContent = text;
    map.replaceChildren(status);
  }

  function syncLinks() {
    switchLink.href = lessonPageUrl(categoryKey, otherView, select.value);
    history.replaceState(null, "", lessonPageUrl(categoryKey, view, select.value));
  }

  function setupPicker(options, selected, onSelect) {
    select.replaceChildren(...options.map(({ key, name }) => new Option(name, key)));
    if (options.some(({ key }) => key === selected)) select.value = selected;
    select.disabled = false;
    function update() {
      syncLinks();
      onSelect();
    }
    select.addEventListener("change", update);
    update();
  }

  async function loadDrugLessons() {
    setLearningStyle(view);
    let drugs;
    try {
      const response = await fetch(`${BASE_URL}/drugs`);
      if (response.status === 404) {
        showStatus("Restart the backend from the current project folder to load the updated drug list, then refresh.");
        return;
      }
      if (!response.ok) throw new Error(`Drug list request failed (${response.status})`);
      drugs = await response.json();
    } catch (error) {
      showStatus("Could not load the drug list. Check that the backend is running, then refresh.");
      return;
    }
    if (!drugs.length) {
      showStatus("No drug lessons are available yet.");
      return;
    }
    setupPicker(drugs, params.get("drug"), () => {
      if (getUsername()) {
        loadPath();
      } else {
        map.innerHTML = '<div class="empty-state">Please <a href="login.html">log in</a>, or go to the ' +
          '<a href="index.html">home page</a> and choose <strong>Try without an account</strong>, to start learning.</div>';
      }
    });
  }

  async function loadTopicOutline() {
    // Existing drug features look for #drugSelect. Use the same control with its own label.
    const label = document.getElementById("lessonPickerLabel");
    select.id = "topicSelect";
    label.htmlFor = select.id;
    label.textContent = "Topic";
    const back = document.getElementById("lessonModesBack");
    back.href = "index.html" + lessonModesHash(categoryKey);
    switchLink.hidden = true;

    let catalog;
    try {
      catalog = await loadLearningCatalog();
    } catch (error) {
      showStatus("Could not load the topics. Refresh the page to try again.");
      return;
    }
    if (!Object.hasOwn(catalog, categoryKey) || !catalog[categoryKey].topics?.length) {
      back.href = "index.html#path";
      back.textContent = "← All lesson categories";
      showStatus("No topics were found for this category. Choose another lesson category.");
      return;
    }
    const category = catalog[categoryKey];
    const modeTitle = view === "game" ? "Game mode" : "Focused lessons";
    document.title = `${category.name} · ${modeTitle} - Grove`;
    document.getElementById("lessonPathTitle").textContent = category.name;
    document.getElementById("lessonPathDescription").textContent = category.description;

    const units = category.skills.map(skill => ({ category: skill, min_crown: 0, unlocked: false }));
    const options = category.topics.map(({ topic_code, title }) => ({ key: topic_code, name: title }));
    let selection = 0;
    setupPicker(options, params.get("topic"), async () => {
      const requestId = ++selection;
      const topic = category.topics.find(entry => entry.topic_code === select.value);
      setLessonSource("outline");
      if (!topic.playable) {
        renderPath(topic.topic_code, { units }, { previewTopic: topic.title });
        return;
      }
      if (!getUsername()) {
        renderPath(topic.topic_code, { units }, { previewTopic: topic.title });
        map.querySelector(".fp-next p").innerHTML =
          '<a href="login.html">Log in</a> or <a href="index.html">try without an account</a> to start this lesson.';
        return;
      }
      showStatus("Loading lessons…");
      try {
        const response = await apiFetch(`${BASE_URL}/topics/${encodeURIComponent(topic.topic_code)}/path`);
        if (requestId !== selection) return;
        if (response.status === 404) {
          showStatus("These lessons need the updated backend and curriculum. Run the database upgrade, then restart the backend.");
          return;
        }
        if (!response.ok) throw new Error(`Topic path request failed (${response.status})`);
        const data = await response.json();
        if (requestId !== selection) return;
        setLessonSource("topic");
        renderPath(topic.topic_code, data, { topicName: data.topic });
      } catch (error) {
        if (requestId === selection) showStatus("Could not load this topic’s lessons. Check the backend, then refresh.");
      }
    });
    switchLink.hidden = false;
  }

  if (categoryKey === "drugs") loadDrugLessons();
  else loadTopicOutline();
})();