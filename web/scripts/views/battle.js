import { imageSrc } from "../imagesrc.js";
import { api } from "../api.js";
import { state, ensurePokemonLoaded, ensureUserResolved, isOwned } from "../state.js";
import { typeChipsRow } from "../typecolors.js";
import { openPicker } from "../components/picker.js";
import { toast } from "../components/toast.js";
import { promptDialog } from "../components/dialog.js";
import { closeIcon } from "../icons.js";

const planner = {
  opponentMode: "single", // 'single' | 'team'
  opponents: [], // array of pokedex numbers (length 1 for single)
  resultTab: "all", // 'all' | 'owned' | 'not_owned'
  rankResults: null,
  generateMode: "owned", // 'owned' | 'unrestricted'
  generated: null,
};

function opponentChips(container) {
  container.textContent = "";
  for (const num of planner.opponents) {
    const p = state.byNumber.get(num);
    const chip = document.createElement("span");
    chip.className = "opponent-chip";
    const img = document.createElement("img");
    img.src = imageSrc(p);
    img.alt = "";
    chip.appendChild(img);
    const label = document.createElement("span");
    label.textContent = p.name;
    chip.appendChild(label);
    const rm = document.createElement("button");
    rm.type = "button";
    rm.appendChild(closeIcon());
    rm.setAttribute("aria-label", `Remove ${p.name} from opponent`);
    rm.addEventListener("click", () => {
      planner.opponents = planner.opponents.filter((n) => n !== num);
      opponentChips(container);
    });
    chip.appendChild(rm);
    container.appendChild(chip);
  }
  const canAddMore = planner.opponentMode === "team" ? planner.opponents.length < 6 : planner.opponents.length < 1;
  if (canAddMore) {
    const add = document.createElement("button");
    add.className = "chip-btn";
    add.textContent = planner.opponents.length ? "+ Add" : "+ Choose opponent";
    add.addEventListener("click", () => {
      openPicker({
        title: "Choose an opposing Pokémon",
        exclude: new Set(planner.opponents),
        onSelect: (p) => {
          if (planner.opponentMode === "single") planner.opponents = [p.pokedex_number];
          else planner.opponents.push(p.pokedex_number);
          opponentChips(container);
        },
      });
    });
    container.appendChild(add);
  }
}

function resultRow(r, rank) {
  const row = document.createElement("div");
  row.className = "result-card result-card--ranked";
  const rankEl = document.createElement("div");
  rankEl.className = "result-card__rank";
  rankEl.textContent = "#" + rank;
  row.appendChild(rankEl);

  const p = state.byNumber.get(r.pokedex_number);
  const art = document.createElement("div");
  art.className = "result-card__art";
  const img = document.createElement("img");
  img.src = imageSrc(p);
  img.alt = "";
  art.appendChild(img);
  row.appendChild(art);

  const mid = document.createElement("div");
  const nameRow = document.createElement("div");
  nameRow.style.display = "flex";
  nameRow.style.alignItems = "center";
  nameRow.style.gap = "0.5rem";
  const name = document.createElement("span");
  name.className = "result-card__name";
  name.textContent = p.name;
  nameRow.appendChild(name);
  if (r.owned) {
    const badge = document.createElement("span");
    badge.className = "field__hint";
    badge.textContent = "✓ Owned";
    nameRow.appendChild(badge);
  }
  mid.appendChild(nameRow);
  mid.appendChild(typeChipsRow(r.types));
  const explain = document.createElement("p");
  explain.className = "result-card__explain";
  explain.textContent = r.explanation;
  mid.appendChild(explain);
  row.appendChild(mid);

  // Score and action share one trailing grid cell -- as separate children
  // they overflowed the grid and wrapped onto a second row.
  const actions = document.createElement("div");
  actions.className = "result-card__actions";
  const score = document.createElement("div");
  score.className = "result-card__score";
  score.textContent = (r.score >= 0 ? "+" : "") + r.score.toFixed(1);
  score.title = "Combined type + stat score (see README for formula)";
  actions.appendChild(score);

  const addBtn = document.createElement("button");
  addBtn.className = "btn btn-ghost btn-sm";
  addBtn.textContent = "Add to a team";
  addBtn.addEventListener("click", async () => {
    try {
      const { teams } = await api.get("/api/teams");
      const target = teams.find((t) => t.members.length < 6 && !t.members.some((m) => m.pokedex_number === r.pokedex_number));
      if (!target) { toast("No team has room. Create one in Team Builder first."); return; }
      const members = [...target.members.map((m) => m.pokedex_number), r.pokedex_number];
      await api.put(`/api/teams/${target.id}`, { members });
      toast(`Added ${p.name} to ${target.name}.`);
    } catch (e) {
      toast(e.message || "Sign in to use teams.");
    }
  });
  actions.appendChild(addBtn);
  row.appendChild(actions);

  return row;
}

async function runRank(root) {
  const resultsBox = root.querySelector("#battle-results");
  if (!planner.opponents.length) {
    resultsBox.innerHTML = `<div class="empty-state"><p class="empty-state__title">Choose an opponent</p><p>Pick a single Pokémon or build an opposing team to see ranked counters.</p></div>`;
    return;
  }
  resultsBox.textContent = "Scoring…";
  const opponent = planner.opponentMode === "single"
    ? { mode: "single", pokedex_number: planner.opponents[0] }
    : { mode: "team", pokedex_numbers: planner.opponents };
  try {
    const data = await api.post("/api/battle/rank", { opponent, filter: planner.resultTab, limit: 20 });
    planner.rankResults = data;
    resultsBox.textContent = "";
    if (!data.results.length) {
      resultsBox.innerHTML = `<div class="empty-state"><p class="empty-state__title">No candidates</p><p>That filter has no eligible Pokémon right now.</p></div>`;
      return;
    }
    data.results.forEach((r, i) => resultsBox.appendChild(resultRow(r, i + 1)));
  } catch (e) {
    resultsBox.innerHTML = `<div class="banner banner-error">${e.message}</div>`;
  }
}

function renderReplacements(container, suggestions) {
  container.textContent = "";
  if (!suggestions || !suggestions.length) return;
  const label = document.createElement("p");
  label.className = "section-label";
  label.textContent = "Unowned Pokémon that would improve this team";
  container.appendChild(label);
  for (const s of suggestions) {
    const card = document.createElement("div");
    card.className = "panel replacement-card";
    const current = state.byNumber.get(s.replaces.pokedex_number);
    const sug = state.byNumber.get(s.suggestion.pokedex_number);
    card.innerHTML = `
      <p><strong>${sug.name}</strong> would replace <strong>${current.name}</strong>
      (score ${s.replaces.score.toFixed(1)} → ${s.suggestion.score.toFixed(1)}, +${s.improvement.toFixed(1)})</p>
      <p class="field__hint">${s.reason}</p>
      <p class="tradeoff-list">Tradeoffs: ${s.tradeoffs.join("; ")}</p>
    `;
    container.appendChild(card);
  }
}

async function runGenerate(root) {
  const box = root.querySelector("#battle-generate-results");
  if (!planner.opponents.length) {
    box.innerHTML = `<div class="empty-state"><p class="empty-state__title">Choose an opponent first</p></div>`;
    return;
  }
  box.textContent = "Building team…";
  const opponent = planner.opponentMode === "single"
    ? { mode: "single", pokedex_number: planner.opponents[0] }
    : { mode: "team", pokedex_numbers: planner.opponents };
  try {
    const data = await api.post("/api/battle/generate", { opponent, mode: planner.generateMode, size: 6 });
    planner.generated = data;
    box.textContent = "";
    if (data.message) {
      const banner = document.createElement("div");
      banner.className = "banner banner-amber";
      banner.textContent = data.message;
      box.appendChild(banner);
    }
    if (!data.members.length) return;
    const grid = document.createElement("div");
    grid.className = "team-grid";
    for (const m of data.members) {
      const slot = document.createElement("div");
      slot.className = "team-slot is-filled";
      slot.innerHTML = `<img src="${imageSrc(m)}" alt="" style="width:3.5rem">
        <div style="font-weight:600;font-size:0.85rem">${m.name}</div>`;
      slot.appendChild(typeChipsRow(m.types));
      if (!m.owned) {
        const flag = document.createElement("div");
        flag.className = "unowned-flag";
        flag.textContent = "Not in your collection";
        slot.appendChild(flag);
      }
      const why = document.createElement("p");
      why.className = "field__hint";
      why.textContent = data.explanations[m.pokedex_number] || "";
      slot.appendChild(why);
      grid.appendChild(slot);
    }
    box.appendChild(grid);

    const replBox = document.createElement("div");
    replBox.style.marginTop = "1.25rem";
    box.appendChild(replBox);
    renderReplacements(replBox, data.replacement_suggestions);

    if (data.members.length) {
      const owned = planner.generateMode === "owned";
      const saveBtn = document.createElement("button");
      saveBtn.className = "btn btn-primary";
      saveBtn.style.marginTop = "1rem";
      saveBtn.textContent = owned ? "Save as a team" : "Save as a planning team";
      saveBtn.addEventListener("click", async () => {
        const name = await promptDialog({
          title: "Save team",
          label: "Team name",
          initialValue: owned ? "Counter team" : "Counter team (planning)",
          confirmLabel: "Save",
          message: owned ? null : "Unowned members will be saved too -- they stay clearly flagged in Team Builder.",
        });
        if (!name) return;
        saveBtn.disabled = true;
        try {
          await api.post("/api/teams", {
            name,
            mode: owned ? "owned" : "manual",
            members: data.members.map((m) => m.pokedex_number),
          });
          toast("Saved to Team Builder.");
        } catch (e) {
          toast(e.message);
        } finally {
          saveBtn.disabled = false;
        }
      });
      box.appendChild(saveBtn);
    }
  } catch (e) {
    box.innerHTML = `<div class="banner banner-error">${e.message}</div>`;
  }
}

export async function renderBattle(root) {
  root.textContent = "";
  await ensureUserResolved();
  await ensurePokemonLoaded();

  const header = document.createElement("div");
  header.className = "view-header";
  header.innerHTML = `<div>
    <h1 class="view-title">Battle planner</h1>
    <p class="view-subtitle">Species- and type-based match-up planning from base stats alone -- not a battle simulator, and it knows nothing about moves or abilities.</p>
  </div>`;
  root.appendChild(header);

  const vsRow = document.createElement("div");
  vsRow.className = "vs-row";
  root.appendChild(vsRow);

  const left = document.createElement("div");
  left.innerHTML = `<p class="field__label" style="margin-bottom:0.4rem">Opponent</p>`;
  const modeToggle = document.createElement("div");
  modeToggle.className = "mode-toggle";
  modeToggle.style.marginBottom = "0.6rem";
  const singleBtn = document.createElement("button");
  singleBtn.textContent = "Single Pokémon";
  const teamBtn = document.createElement("button");
  teamBtn.textContent = "Team (up to 6)";
  modeToggle.append(singleBtn, teamBtn);
  left.appendChild(modeToggle);
  const chips = document.createElement("div");
  chips.className = "opponent-slots";
  left.appendChild(chips);
  vsRow.appendChild(left);

  const vsMark = document.createElement("div");
  vsMark.className = "vs-mark";
  vsMark.textContent = "VS";
  vsRow.appendChild(vsMark);

  const right = document.createElement("div");
  right.innerHTML = `<p class="field__hint">Your picks don't need to be owned -- this is unrestricted opponent scouting.</p>`;
  vsRow.appendChild(right);

  function syncModeButtons() {
    singleBtn.classList.toggle("is-active", planner.opponentMode === "single");
    teamBtn.classList.toggle("is-active", planner.opponentMode === "team");
  }
  singleBtn.addEventListener("click", () => {
    planner.opponentMode = "single";
    if (planner.opponents.length > 1) planner.opponents = planner.opponents.slice(0, 1);
    syncModeButtons(); opponentChips(chips);
  });
  teamBtn.addEventListener("click", () => { planner.opponentMode = "team"; syncModeButtons(); opponentChips(chips); });
  syncModeButtons();
  opponentChips(chips);

  const tabs = document.createElement("div");
  tabs.className = "tab-row";
  tabs.innerHTML = `<h2 style="font-family:var(--font-display);font-weight:700;font-size:1.4rem;margin-right:auto">Ranked counters</h2>`;
  root.appendChild(tabs);

  const tabRow = document.createElement("div");
  tabRow.className = "chip-row";
  root.appendChild(tabRow);
  const tabDefs = [["all", "All"], ["owned", "Owned"], ["not_owned", "Not owned"]];
  for (const [key, label] of tabDefs) {
    const btn = document.createElement("button");
    btn.className = "chip-btn" + (planner.resultTab === key ? " is-active" : "");
    btn.textContent = label;
    btn.addEventListener("click", () => {
      planner.resultTab = key;
      [...tabRow.children].forEach((c) => c.classList.remove("is-active"));
      btn.classList.add("is-active");
      runRank(root);
    });
    tabRow.appendChild(btn);
  }

  const rankBtn = document.createElement("button");
  rankBtn.className = "btn btn-primary";
  rankBtn.style.margin = "0.75rem 0 1rem";
  rankBtn.textContent = "Rank counters";
  rankBtn.addEventListener("click", () => runRank(root));
  root.appendChild(rankBtn);

  const resultsBox = document.createElement("div");
  resultsBox.id = "battle-results";
  root.appendChild(resultsBox);
  resultsBox.innerHTML = `<div class="empty-state"><p class="empty-state__title">Choose an opponent</p><p>Pick a single Pokémon or build an opposing team, then rank counters.</p></div>`;

  const genHeader = document.createElement("h2");
  genHeader.style.cssText = "font-family:var(--font-display);font-weight:700;font-size:1.4rem;margin:2rem 0 0.75rem";
  genHeader.textContent = "Generate a complementary team";
  root.appendChild(genHeader);

  if (state.user === null) {
    const banner = document.createElement("div");
    banner.className = "banner banner-info";
    banner.textContent = "Sign in to generate a team from your collection. You can still rank counters above without an account.";
    root.appendChild(banner);
  } else {
    const genToggle = document.createElement("div");
    genToggle.className = "mode-toggle";
    genToggle.style.marginBottom = "0.75rem";
    const ownedGenBtn = document.createElement("button");
    ownedGenBtn.textContent = "Owned only";
    const anyGenBtn = document.createElement("button");
    anyGenBtn.textContent = "Unrestricted";
    genToggle.append(ownedGenBtn, anyGenBtn);
    root.appendChild(genToggle);
    function syncGen() {
      ownedGenBtn.classList.toggle("is-active", planner.generateMode === "owned");
      anyGenBtn.classList.toggle("is-active", planner.generateMode === "unrestricted");
    }
    ownedGenBtn.addEventListener("click", () => { planner.generateMode = "owned"; syncGen(); });
    anyGenBtn.addEventListener("click", () => { planner.generateMode = "unrestricted"; syncGen(); });
    syncGen();

    const genBtn = document.createElement("button");
    genBtn.className = "btn btn-amber";
    genBtn.style.margin = "0.75rem 0 1rem";
    genBtn.textContent = "Generate team";
    genBtn.addEventListener("click", () => runGenerate(root));
    root.appendChild(genBtn);
  }

  const genResults = document.createElement("div");
  genResults.id = "battle-generate-results";
  root.appendChild(genResults);

  if (state.user) {
    const checkHeader = document.createElement("h2");
    checkHeader.style.cssText = "font-family:var(--font-display);font-weight:700;font-size:1.4rem;margin:2rem 0 0.75rem";
    checkHeader.textContent = "Check a saved team against this opponent";
    root.appendChild(checkHeader);

    const checkRow = document.createElement("div");
    checkRow.style.cssText = "display:flex;gap:0.5rem;align-items:center;flex-wrap:wrap";
    const teamSelect = document.createElement("select");
    teamSelect.className = "select";
    teamSelect.style.width = "auto";
    teamSelect.setAttribute("aria-label", "Pick a saved owned-mode team");
    const checkBtn = document.createElement("button");
    checkBtn.className = "btn btn-ghost";
    checkBtn.textContent = "Find upgrades";
    checkRow.append(teamSelect, checkBtn);
    root.appendChild(checkRow);

    const checkResults = document.createElement("div");
    checkResults.style.marginTop = "1rem";
    root.appendChild(checkResults);

    let ownedTeams = [];
    try {
      const { teams } = await api.get("/api/teams");
      ownedTeams = teams.filter((t) => t.mode === "owned" && t.members.length);
    } catch { /* not signed in somehow; ignore */ }

    if (!ownedTeams.length) {
      teamSelect.disabled = true;
      checkBtn.disabled = true;
      teamSelect.add(new Option("No saved owned-mode teams yet", ""));
    } else {
      for (const t of ownedTeams) teamSelect.add(new Option(`${t.name} (${t.members.length}/6)`, String(t.id)));
    }

    checkBtn.addEventListener("click", async () => {
      if (!planner.opponents.length) {
        checkResults.innerHTML = `<div class="banner banner-error">Choose an opponent above first.</div>`;
        return;
      }
      const team = ownedTeams.find((t) => String(t.id) === teamSelect.value);
      if (!team) return;
      const opponent = planner.opponentMode === "single"
        ? { mode: "single", pokedex_number: planner.opponents[0] }
        : { mode: "team", pokedex_numbers: planner.opponents };
      checkResults.textContent = "Checking…";
      try {
        const data = await api.post("/api/battle/replacements", {
          opponent, team: team.members.map((m) => m.pokedex_number),
        });
        checkResults.textContent = "";
        if (!data.suggestions.length) {
          checkResults.innerHTML = `<div class="banner banner-info">No unowned Pokémon would clearly improve this team's weakest matchups -- it already holds up well.</div>`;
        } else {
          renderReplacements(checkResults, data.suggestions);
        }
      } catch (e) {
        checkResults.innerHTML = `<div class="banner banner-error">${e.message}</div>`;
      }
    });
  }
}
