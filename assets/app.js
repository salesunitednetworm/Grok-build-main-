const STORAGE_KEY = "sun-portal-v1";

const defaultState = {
  note: "",
  deals: [
    { id: "d1", name: "Oakridge lots for a production builder", stage: "talk" },
    { id: "d2", name: "West-end infill parcel", stage: "active" },
    { id: "d3", name: "Waterfront lot package", stage: "hold" },
  ],
  sites: [
    { id: "s1", name: "Lot 18 · Ridgeview", place: "Sample area" },
    { id: "s2", name: "Concession block", place: "Sample township" },
  ],
};

const stages = [
  { id: "talk", label: "Conversation" },
  { id: "active", label: "In work" },
  { id: "hold", label: "On hold" },
];

const titles = {
  home: ["Portal", "Home"],
  pipeline: ["Sales", "Pipeline"],
  sites: ["Inventory", "Sites"],
  tools: ["Workspace", "Tools"],
  team: ["People", "Team"],
};

function loadState() {
  try {
    return { ...defaultState, ...JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}") };
  } catch {
    return structuredClone(defaultState);
  }
}

function saveState(state) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

let state = loadState();

function route() {
  const name = (location.hash.replace("#/", "") || "home");
  const known = titles[name] ? name : "home";
  document.querySelectorAll(".view").forEach((view) => {
    view.hidden = view.id !== `view-${known}`;
  });
  document.querySelectorAll(".nav a").forEach((link) => {
    link.classList.toggle("active", link.dataset.route === known);
  });
  const [eyebrow, title] = titles[known];
  document.getElementById("page-eyebrow").textContent = eyebrow;
  document.getElementById("page-title").textContent = title;
}

function renderHome() {
  document.getElementById("today").textContent = new Date().toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
  document.getElementById("stat-deals").textContent = String(state.deals.length);
  document.getElementById("stat-sites").textContent = String(state.sites.length);
  document.getElementById("focus-list").innerHTML = [
    `${state.deals.filter((deal) => deal.stage === "active").length} deal(s) in work`,
    `${state.sites.length} site(s) on the board`,
    "Presite is not connected",
  ]
    .map((item) => `<li>${item}</li>`)
    .join("");
  document.getElementById("saved-note").textContent = state.note
    ? `Saved: ${escapeHtml(state.note)}`
    : "No team note yet.";
}

function renderPipeline() {
  const query = document.getElementById("deal-search").value.trim().toLowerCase();
  const board = document.getElementById("deal-board");
  board.innerHTML = stages
    .map((stage) => {
      const cards = state.deals
        .filter((deal) => deal.stage === stage.id)
        .filter((deal) => deal.name.toLowerCase().includes(query))
        .map((deal) => {
          const buttons = stages
            .filter((item) => item.id !== deal.stage)
            .map((item) => `<button type="button" data-move="${deal.id}:${item.id}">${item.label}</button>`)
            .join("");
          return `<article class="card"><strong>${escapeHtml(deal.name)}</strong><div>${buttons}</div></article>`;
        })
        .join("");
      return `<section class="column"><h3>${stage.label}</h3>${cards || "<p class='hint'>Nothing here.</p>"}</section>`;
    })
    .join("");
}

function renderSites() {
  document.getElementById("site-cards").innerHTML = state.sites
    .map(
      (site) =>
        `<article class="card"><h3>${escapeHtml(site.name)}</h3><p>${escapeHtml(site.place || "Location to add")}</p></article>`
    )
    .join("");
}

function render() {
  renderHome();
  renderPipeline();
  renderSites();
}

document.getElementById("note-form").addEventListener("submit", (event) => {
  event.preventDefault();
  state.note = document.getElementById("note-input").value.trim();
  saveState(state);
  renderHome();
});

document.getElementById("deal-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const name = document.getElementById("deal-name").value.trim();
  state.deals.unshift({ id: crypto.randomUUID(), name, stage: "talk" });
  document.getElementById("deal-name").value = "";
  saveState(state);
  render();
});

document.getElementById("deal-search").addEventListener("input", renderPipeline);

document.getElementById("deal-board").addEventListener("click", (event) => {
  const value = event.target.getAttribute("data-move");
  if (!value) return;
  const [id, stage] = value.split(":");
  state.deals = state.deals.map((deal) => (deal.id === id ? { ...deal, stage } : deal));
  saveState(state);
  render();
});

document.getElementById("site-form").addEventListener("submit", (event) => {
  event.preventDefault();
  state.sites.unshift({
    id: crypto.randomUUID(),
    name: document.getElementById("site-name").value.trim(),
    place: document.getElementById("site-place").value.trim(),
  });
  event.target.reset();
  saveState(state);
  render();
});

document.getElementById("copy-link").addEventListener("click", async () => {
  const button = document.getElementById("copy-link");
  try {
    await navigator.clipboard.writeText(location.href.split("#")[0]);
    button.textContent = "Link copied";
  } catch {
    button.textContent = location.href.split("#")[0];
  }
});

window.addEventListener("hashchange", route);
route();
render();
