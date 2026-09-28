const STORAGE_KEY = "sun-portal-v1";
const SESSION_KEY = "sun-portal-session";
const ACCESS_CODE = "UNITED2026";

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

function currentSession() {
  try {
    return JSON.parse(sessionStorage.getItem(SESSION_KEY) || "null");
  } catch {
    return null;
  }
}

function showPortal(session) {
  document.getElementById("login-screen").hidden = true;
  document.getElementById("portal-app").hidden = false;
  const roleLabel = session.role === "partner" ? "Partner" : "Investor";
  document.getElementById("who-label").textContent = `${roleLabel} · ${session.email}`;
  route();
  render();
}

function showLogin(message) {
  document.getElementById("portal-app").hidden = true;
  document.getElementById("login-screen").hidden = false;
  document.getElementById("login-error").textContent = message || "";
}

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

document.getElementById("login-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const role = document.querySelector('input[name="role"]:checked').value;
  const email = document.getElementById("login-email").value.trim();
  const code = document.getElementById("login-code").value.trim().toUpperCase();
  if (code !== ACCESS_CODE) {
    showLogin("That access code is not right. Ask Wayne for the investor or partner code.");
    return;
  }
  const session = { role, email };
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  showPortal(session);
});

document.getElementById("sign-out").addEventListener("click", () => {
  sessionStorage.removeItem(SESSION_KEY);
  document.getElementById("login-form").reset();
  showLogin("");
});

window.addEventListener("hashchange", () => {
  if (currentSession()) route();
});

const session = currentSession();
if (session) {
  showPortal(session);
} else {
  showLogin("");
}
