import { imageSrc } from "../imagesrc.js";
import { api } from "../api.js";
import { state, isOwned, refreshCollection } from "../state.js";
import { typeChipsRow } from "../typecolors.js";
import { toast } from "./toast.js";
import { trapFocus } from "./a11y.js";
import { closeIcon } from "../icons.js";

const STAT_LABELS = [
  ["hp", "HP"], ["attack", "Attack"], ["defense", "Defense"],
  ["special_attack", "Sp. Atk"], ["special_defense", "Sp. Def"], ["speed", "Speed"],
];
const STAT_MAX = 180;

function fmtMult(m) {
  if (m === 1) return "1x";
  if (Number.isInteger(m)) return m + "x";
  return m + "x";
}

export async function openDetail(pokedexNumber, { onChanged } = {}) {
  const trigger = document.activeElement;
  const p = state.byNumber.get(pokedexNumber);
  if (!p) return;

  const scrim = document.createElement("div");
  scrim.className = "scrim";
  const drawer = document.createElement("div");
  drawer.className = "drawer";
  drawer.setAttribute("role", "dialog");
  drawer.setAttribute("aria-modal", "true");
  drawer.setAttribute("aria-label", `${p.name} specimen sheet`);

  const head = document.createElement("div");
  head.className = "drawer__head";
  const num = document.createElement("span");
  num.className = "drawer__num";
  num.textContent = "No. " + String(p.pokedex_number).padStart(4, "0");
  const close = document.createElement("button");
  close.type = "button";
  close.className = "drawer__close";
  close.appendChild(closeIcon());
  close.setAttribute("aria-label", "Close specimen sheet");
  head.append(num, close);
  drawer.appendChild(head);

  const body = document.createElement("div");
  body.className = "drawer__body";

  const art = document.createElement("div");
  art.className = "drawer__art";
  const img = document.createElement("img");
  img.src = imageSrc(p);
  img.alt = "";
  art.appendChild(img);
  body.appendChild(art);

  const name = document.createElement("h2");
  name.className = "drawer__name";
  name.textContent = p.name;
  body.appendChild(name);

  const genus = document.createElement("p");
  genus.className = "drawer__genus";
  genus.textContent = `${p.genus} · Generation ${p.generation}`;
  body.appendChild(genus);

  body.appendChild(typeChipsRow(p.types));

  const actions = document.createElement("div");
  actions.className = "drawer__actions";
  body.appendChild(actions);

  function renderActions() {
    actions.textContent = "";
    if (state.user === null) {
      const hint = document.createElement("p");
      hint.className = "field__hint";
      hint.textContent = "Sign in to add this Pokémon to your collection or a team.";
      actions.appendChild(hint);
      return;
    }
    const owned = isOwned(p.pokedex_number);
    const collectBtn = document.createElement("button");
    collectBtn.className = "btn " + (owned ? "btn-ghost" : "btn-primary");
    collectBtn.textContent = owned ? "Remove from collection" : "Add to collection";
    collectBtn.addEventListener("click", async () => {
      if (owned) await api.del(`/api/collection/${p.pokedex_number}`);
      else await api.post("/api/collection", { pokedex_number: p.pokedex_number });
      await refreshCollection();
      toast(owned ? `Removed ${p.name} from your collection.` : `Added ${p.name} to your collection.`);
      renderActions();
      onChanged?.();
    });
    actions.appendChild(collectBtn);

    const teamBtn = document.createElement("button");
    teamBtn.className = "btn btn-ghost";
    teamBtn.textContent = "Add to a team";
    teamBtn.addEventListener("click", () => addToTeamFlow(p));
    actions.appendChild(teamBtn);
  }
  renderActions();

  body.appendChild(Object.assign(document.createElement("h3"), { className: "section-label", textContent: "Base stats" }));
  for (const [key, label] of STAT_LABELS) {
    const value = p.stats[key];
    const row = document.createElement("div");
    row.className = "stat-row";
    row.innerHTML = `
      <span class="stat-row__label">${label}</span>
      <span class="stat-row__track"><span class="stat-row__fill" style="width:${Math.min(100, (value / STAT_MAX) * 100)}%"></span></span>
      <span class="stat-row__value">${value}</span>`;
    body.appendChild(row);
  }
  const totalRow = document.createElement("p");
  totalRow.className = "field__hint";
  totalRow.textContent = `Total: ${p.total_stats} · Height ${p.height_m} m · Weight ${p.weight_kg} kg`;
  body.appendChild(totalRow);

  body.appendChild(Object.assign(document.createElement("h3"), { className: "section-label", textContent: "Type weaknesses & resistances" }));
  const matchupBox = document.createElement("div");
  matchupBox.className = "matchup-grid";
  matchupBox.textContent = "Loading…";
  body.appendChild(matchupBox);

  drawer.appendChild(body);

  let untrap;
  function onKey(e) {
    if (e.key === "Escape") teardown();
  }
  function teardown() {
    untrap?.();
    document.removeEventListener("keydown", onKey);
    scrim.remove();
    drawer.remove();
    if (trigger && trigger.focus) trigger.focus();
  }
  scrim.addEventListener("click", teardown);
  close.addEventListener("click", teardown);
  document.addEventListener("keydown", onKey);

  document.body.append(scrim, drawer);
  untrap = trapFocus(drawer);
  close.focus();

  const { buckets } = await api.get(`/api/pokemon/${p.pokedex_number}/matchup`);
  matchupBox.textContent = "";
  const order = [4, 2, 0.5, 0.25, 0];
  const seen = new Set();
  for (const mult of order) {
    const types = buckets[String(mult)] || buckets[mult];
    if (!types || !types.length) continue;
    seen.add(mult);
    const row = document.createElement("div");
    row.className = "matchup-row mult-" + String(mult).replace(".", "\\.");
    row.innerHTML = `<span class="matchup-row__mult">${fmtMult(mult)}</span>`;
    const typesWrap = document.createElement("span");
    typesWrap.className = "matchup-row__types";
    typesWrap.appendChild(typeChipsRow(types));
    row.appendChild(typesWrap);
    matchupBox.appendChild(row);
  }
  if (!matchupBox.children.length) {
    matchupBox.textContent = "Neutral against every type.";
  }
}

async function addToTeamFlow(p) {
  const trigger = document.activeElement;
  let teams = [];
  try {
    const res = await api.get("/api/teams");
    teams = res.teams;
  } catch {
    toast("Sign in to use teams.");
    return;
  }
  const scrim = document.createElement("div");
  scrim.className = "scrim";
  scrim.style.zIndex = "35";
  const box = document.createElement("div");
  box.className = "panel modal-dialog";
  box.style.zIndex = "36";
  box.setAttribute("role", "dialog");
  box.setAttribute("aria-modal", "true");
  box.setAttribute("aria-label", "Add to a team");

  const title = document.createElement("h3");
  title.className = "section-label";
  title.textContent = `Add ${p.name} to…`;
  box.appendChild(title);

  const list = document.createElement("div");
  box.appendChild(list);

  let untrap;
  function onKey(e) {
    if (e.key === "Escape") teardown();
  }
  function teardown() {
    untrap?.();
    document.removeEventListener("keydown", onKey);
    scrim.remove();
    box.remove();
    if (trigger && trigger.focus) trigger.focus();
  }

  const eligible = teams.filter((t) => t.members.length < 6 && !t.members.some((m) => m.pokedex_number === p.pokedex_number));
  if (eligible.length === 0) {
    const empty = document.createElement("p");
    empty.className = "field__hint";
    empty.textContent = "No team has room yet (or already has this Pokémon). Create or edit a team from Team Builder.";
    list.appendChild(empty);
  }
  for (const t of eligible) {
    const btn = document.createElement("button");
    btn.className = "btn btn-ghost btn-block";
    btn.style.marginBottom = "0.4rem";
    btn.textContent = `${t.name} (${t.members.length}/6)`;
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      const members = [...t.members.map((m) => m.pokedex_number), p.pokedex_number];
      try {
        await api.put(`/api/teams/${t.id}`, { members });
        toast(`Added ${p.name} to ${t.name}.`);
        teardown();
      } catch (e) {
        btn.disabled = false;
        toast(e.message);
      }
    });
    list.appendChild(btn);
  }

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "btn btn-ghost btn-block";
  cancel.textContent = "Cancel";
  cancel.style.marginTop = "0.5rem";
  cancel.addEventListener("click", teardown);
  box.appendChild(cancel);

  scrim.addEventListener("click", teardown);
  document.addEventListener("keydown", onKey);
  document.body.append(scrim, box);
  untrap = trapFocus(box);
  (list.querySelector("button") || cancel).focus();
}
