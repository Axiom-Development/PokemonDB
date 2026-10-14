import { api } from "../api.js";
import { state, ensurePokemonLoaded, ensureUserResolved, isOwned } from "../state.js";
import { typeChipsRow } from "../typecolors.js";
import { openPicker } from "../components/picker.js";
import { toast } from "../components/toast.js";
import { confirmDialog } from "../components/dialog.js";
import { closeIcon } from "../icons.js";

let draft = null; // { id, name, mode: 'manual'|'owned', members: [numbers] }
let savedTeams = [];

function newDraft() {
  return { id: null, name: "New team", mode: "manual", members: [] };
}

function memberCard(num, { onRemove }) {
  const p = state.byNumber.get(num);
  const owned = isOwned(num);
  const slot = document.createElement("div");
  slot.className = "team-slot is-filled";
  const img = document.createElement("img");
  img.src = "/" + p.image_path;
  img.alt = "";
  img.style.width = "3.5rem";
  slot.appendChild(img);
  const name = document.createElement("div");
  name.style.fontWeight = "600";
  name.style.fontSize = "0.85rem";
  name.textContent = p.name;
  slot.appendChild(name);
  slot.appendChild(typeChipsRow(p.types));
  if (!owned) {
    const flag = document.createElement("div");
    flag.className = "unowned-flag";
    flag.textContent = "Not in your collection";
    slot.appendChild(flag);
  }
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "team-slot__remove";
  remove.setAttribute("aria-label", `Remove ${p.name} from team`);
  remove.appendChild(closeIcon());
  remove.addEventListener("click", () => onRemove(num));
  slot.appendChild(remove);
  return slot;
}

function emptySlot(onAdd, disabled) {
  const slot = document.createElement("button");
  slot.type = "button";
  slot.className = "team-slot";
  slot.innerHTML = `<span class="team-slot__add">+ Add Pokémon</span>`;
  if (disabled) { slot.disabled = true; slot.style.opacity = "0.4"; }
  else slot.addEventListener("click", onAdd);
  return slot;
}

function renderCoverage(container, analysis) {
  container.innerHTML = "";
  if (!analysis) {
    container.innerHTML = `<p class="field__hint">Add at least one Pokémon to see coverage.</p>`;
    return;
  }
  const covLabel = document.createElement("p");
  covLabel.className = "section-label";
  covLabel.textContent = "Offensive type coverage (best STAB multiplier vs. each type)";
  container.appendChild(covLabel);
  const covGrid = document.createElement("div");
  covGrid.className = "coverage-grid";
  for (const [type, mult] of Object.entries(analysis.offense_coverage)) {
    const cell = document.createElement("div");
    cell.className = "coverage-cell";
    cell.innerHTML = `${type}<span class="coverage-cell__mult">${mult}x</span>`;
    covGrid.appendChild(cell);
  }
  container.appendChild(covGrid);

  const weakLabel = document.createElement("p");
  weakLabel.className = "section-label";
  weakLabel.textContent = "Shared weaknesses (2+ members both hit for 2x or more)";
  container.appendChild(weakLabel);
  const entries = Object.entries(analysis.shared_weaknesses);
  if (!entries.length) {
    container.appendChild(Object.assign(document.createElement("p"), { className: "field__hint", textContent: "None -- no type hits two or more members hard at once." }));
  } else {
    const row = document.createElement("div");
    row.className = "chip-row";
    for (const [type, count] of entries) {
      const chip = document.createElement("span");
      chip.className = "chip-btn is-active";
      chip.textContent = `${type} × ${count}`;
      row.appendChild(chip);
    }
    container.appendChild(row);
  }

  const statsLabel = document.createElement("p");
  statsLabel.className = "section-label";
  statsLabel.textContent = "Average base stats";
  container.appendChild(statsLabel);
  const statsRow = document.createElement("p");
  statsRow.className = "field__hint";
  const a = analysis.stat_averages;
  statsRow.textContent = `HP ${a.hp} · Atk ${a.attack} · Def ${a.defense} · SpA ${a.special_attack} · SpD ${a.special_defense} · Spe ${a.speed}`;
  container.appendChild(statsRow);
}

async function renderEditor(root) {
  root.textContent = "";
  const panel = document.createElement("div");
  panel.className = "panel";

  const nameRow = document.createElement("div");
  nameRow.className = "field";
  nameRow.innerHTML = `<label class="field__label" for="team-name">Team name</label>`;
  const nameInput = document.createElement("input");
  nameInput.className = "input";
  nameInput.id = "team-name";
  nameInput.value = draft.name;
  nameInput.maxLength = 40;
  nameRow.appendChild(nameInput);
  panel.appendChild(nameRow);

  const modeRow = document.createElement("div");
  modeRow.style.marginBottom = "1rem";
  modeRow.innerHTML = `<p class="field__label" style="margin-bottom:0.4rem">Mode</p>`;
  const toggle = document.createElement("div");
  toggle.className = "mode-toggle";
  const manualBtn = document.createElement("button");
  manualBtn.textContent = "Manual (any Pokémon)";
  const ownedBtn = document.createElement("button");
  ownedBtn.textContent = "My collection only";
  toggle.append(manualBtn, ownedBtn);
  modeRow.appendChild(toggle);
  const modeHint = document.createElement("p");
  modeHint.className = "field__hint";
  modeHint.style.marginTop = "0.4rem";
  modeRow.appendChild(modeHint);
  panel.appendChild(modeRow);

  const slotsGrid = document.createElement("div");
  slotsGrid.className = "team-grid";
  panel.appendChild(slotsGrid);

  const genRow = document.createElement("div");
  genRow.style.margin = "1rem 0";
  genRow.style.display = "flex";
  genRow.style.gap = "0.5rem";
  genRow.style.flexWrap = "wrap";
  const autoOwned = document.createElement("button");
  autoOwned.className = "btn btn-ghost";
  autoOwned.textContent = "Auto-build from my collection";
  const autoAny = document.createElement("button");
  autoAny.className = "btn btn-ghost";
  autoAny.textContent = "Auto-build from full Pokédex";
  genRow.append(autoOwned, autoAny);
  panel.appendChild(genRow);

  const genMessage = document.createElement("p");
  genMessage.className = "field__hint";
  panel.appendChild(genMessage);

  const coverage = document.createElement("div");
  panel.appendChild(coverage);

  const actionsRow = document.createElement("div");
  actionsRow.style.display = "flex";
  actionsRow.style.gap = "0.5rem";
  actionsRow.style.marginTop = "1.5rem";
  const saveBtn = document.createElement("button");
  saveBtn.className = "btn btn-primary";
  saveBtn.textContent = draft.id ? "Save changes" : "Save team";
  const cancelBtn = document.createElement("button");
  cancelBtn.className = "btn btn-ghost";
  cancelBtn.textContent = "Cancel";
  actionsRow.append(saveBtn, cancelBtn);
  panel.appendChild(actionsRow);

  root.appendChild(panel);

  async function refreshAnalysis() {
    if (!draft.members.length) { renderCoverage(coverage, null); return; }
    const { analysis } = await api.post("/api/teams/analyze", { members: draft.members });
    renderCoverage(coverage, analysis);
  }

  function renderSlots() {
    slotsGrid.textContent = "";
    for (const num of draft.members) {
      slotsGrid.appendChild(memberCard(num, {
        onRemove: (n) => { draft.members = draft.members.filter((x) => x !== n); renderSlots(); refreshAnalysis(); },
      }));
    }
    for (let i = draft.members.length; i < 6; i++) {
      slotsGrid.appendChild(emptySlot(() => {
        const exclude = new Set(draft.members);
        openPicker({
          title: draft.mode === "owned" ? "Add from your collection" : "Add a Pokémon",
          exclude: draft.mode === "owned"
            ? new Set(state.pokemon.filter((p) => !p.owned).map((p) => p.pokedex_number).concat([...exclude]))
            : exclude,
          onSelect: (p) => { draft.members.push(p.pokedex_number); renderSlots(); refreshAnalysis(); },
        });
      }, false));
    }
  }

  function renderModeUI() {
    manualBtn.classList.toggle("is-active", draft.mode === "manual");
    ownedBtn.classList.toggle("is-active", draft.mode === "owned");
    modeHint.textContent = draft.mode === "owned"
      ? "Only Pokémon already in your collection can be added or auto-built here."
      : "Any Pokémon can be added. Ones you don't own yet are clearly flagged.";
  }

  manualBtn.addEventListener("click", () => { draft.mode = "manual"; renderModeUI(); });
  ownedBtn.addEventListener("click", () => {
    const stray = draft.members.filter((n) => !isOwned(n));
    if (stray.length) {
      toast("Remove unowned members before switching to collection-only mode.");
      return;
    }
    draft.mode = "owned"; renderModeUI();
  });

  autoOwned.addEventListener("click", async () => {
    const { members, shortfall, message } = await api.post("/api/teams/generate", { mode: "owned", size: 6 });
    draft.mode = "owned";
    draft.members = members.map((m) => m.pokedex_number);
    renderModeUI(); renderSlots(); refreshAnalysis();
    genMessage.textContent = message || (shortfall ? "Collection too small for a full team." : "");
  });
  autoAny.addEventListener("click", async () => {
    const { members, shortfall, message } = await api.post("/api/teams/generate", { mode: "unrestricted", size: 6 });
    draft.mode = "manual";
    draft.members = members.map((m) => m.pokedex_number);
    renderModeUI(); renderSlots(); refreshAnalysis();
    genMessage.textContent = message || "";
  });

  saveBtn.addEventListener("click", async () => {
    const name = nameInput.value.trim() || "Untitled team";
    saveBtn.disabled = true;
    try {
      if (draft.id) await api.put(`/api/teams/${draft.id}`, { name, mode: draft.mode, members: draft.members });
      else await api.post("/api/teams", { name, mode: draft.mode, members: draft.members });
      toast("Team saved.");
      draft = null;
      await loadTeams();
      renderList(root);
    } catch (e) {
      toast(e.message);
    } finally {
      saveBtn.disabled = false;
    }
  });
  cancelBtn.addEventListener("click", () => {
    draft = null;
    renderList(root);
  });

  renderModeUI();
  renderSlots();
  refreshAnalysis();
}

function teamSummaryCard(team) {
  const card = document.createElement("div");
  card.className = "panel";
  const head = document.createElement("div");
  head.style.display = "flex";
  head.style.justifyContent = "space-between";
  head.style.alignItems = "center";
  head.innerHTML = `<div>
    <h3 style="font-family:var(--font-display);font-weight:700;font-size:1.2rem">${team.name}</h3>
    <p class="field__hint">${team.mode === "owned" ? "Owned-only" : "Manual"} · ${team.members.length}/6 members</p>
  </div>`;
  const actions = document.createElement("div");
  actions.style.display = "flex";
  actions.style.gap = "0.4rem";
  const editBtn = document.createElement("button");
  editBtn.className = "btn btn-ghost btn-sm";
  editBtn.textContent = "Edit";
  editBtn.addEventListener("click", () => {
    draft = { id: team.id, name: team.name, mode: team.mode, members: team.members.map((m) => m.pokedex_number) };
    renderEditor(card.closest(".view").querySelector("#teams-editor-mount"));
  });
  const delBtn = document.createElement("button");
  delBtn.className = "btn btn-danger btn-sm";
  delBtn.textContent = "Delete";
  delBtn.addEventListener("click", async () => {
    const confirmed = await confirmDialog({
      title: "Delete team",
      message: `Delete "${team.name}"? This can't be undone.`,
      confirmLabel: "Delete",
      cancelLabel: "Cancel",
      danger: true,
    });
    if (!confirmed) return;
    delBtn.disabled = true;
    try {
      await api.del(`/api/teams/${team.id}`);
      await loadTeams();
      renderList(card.closest(".view").querySelector("#teams-editor-mount"));
    } catch (e) {
      delBtn.disabled = false;
      toast(e.message);
    }
  });
  actions.append(editBtn, delBtn);
  head.appendChild(actions);
  card.appendChild(head);

  const thumbs = document.createElement("div");
  thumbs.style.display = "flex";
  thumbs.style.gap = "0.4rem";
  thumbs.style.marginTop = "0.6rem";
  for (const m of team.members) {
    const img = document.createElement("img");
    img.src = "/" + m.image_path;
    img.alt = m.name;
    img.title = m.name;
    img.style.width = "3rem";
    img.style.background = "var(--parchment-dim)";
    img.style.borderRadius = "var(--radius-sm)";
    thumbs.appendChild(img);
  }
  if (!team.members.length) {
    thumbs.innerHTML = `<p class="field__hint">Empty team.</p>`;
  }
  card.appendChild(thumbs);

  if (team.analysis && Object.keys(team.analysis.shared_weaknesses).length) {
    const weak = document.createElement("p");
    weak.className = "field__hint";
    weak.style.marginTop = "0.5rem";
    weak.textContent = "Shared weaknesses: " + Object.entries(team.analysis.shared_weaknesses).map(([t, c]) => `${t} (${c})`).join(", ");
    card.appendChild(weak);
  }
  return card;
}

async function loadTeams() {
  const { teams } = await api.get("/api/teams");
  savedTeams = teams;
}

function renderList(mount) {
  mount.textContent = "";
  const listWrap = document.createElement("div");
  listWrap.id = "teams-list";

  const newBtn = document.createElement("button");
  newBtn.className = "btn btn-primary";
  newBtn.style.marginBottom = "1rem";
  newBtn.textContent = "+ New team";
  newBtn.addEventListener("click", () => {
    draft = newDraft();
    renderEditor(mount);
  });
  listWrap.appendChild(newBtn);

  if (!savedTeams.length) {
    // insertAdjacentHTML appends parsed markup without touching existing
    // children -- unlike `innerHTML +=`, which re-serializes and reparses
    // the whole subtree and so silently detaches newBtn's click listener.
    listWrap.insertAdjacentHTML("beforeend", `<div class="empty-state">
      <p class="empty-state__title">No teams yet</p>
      <p>Build your first team manually or auto-build one from your collection or the full Pokédex.</p>
    </div>`);
  } else {
    for (const t of savedTeams) listWrap.appendChild(teamSummaryCard(t));
  }
  mount.appendChild(listWrap);
}

export async function renderTeams(root) {
  root.textContent = "";
  await ensureUserResolved();
  if (state.user === null) {
    root.innerHTML = `
      <div class="view-header"><div><h1 class="view-title">Team builder</h1></div></div>
      <div class="empty-state">
        <p class="empty-state__title">Sign in to build teams</p>
        <p>Teams are saved to your account so you can come back to them later.</p>
        <p style="margin-top:1rem"><a class="btn btn-primary" href="#/account">Go to account</a></p>
      </div>`;
    return;
  }

  const header = document.createElement("div");
  header.className = "view-header";
  header.innerHTML = `<div>
    <h1 class="view-title">Team builder</h1>
    <p class="view-subtitle">Plan up to six Pokémon, save named teams, and see type coverage and shared weaknesses before you commit.</p>
  </div>`;
  root.appendChild(header);

  const mount = document.createElement("div");
  mount.id = "teams-editor-mount";
  root.appendChild(mount);

  await ensurePokemonLoaded();
  await loadTeams();
  if (draft) await renderEditor(mount);
  else renderList(mount);
}
