import { state, ensurePokemonLoaded } from "../state.js";
import { specimenCard } from "../components/pokecard.js";
import { openDetail } from "../components/detail.js";
import { TYPE_ORDER } from "../typecolors.js";

const SORTS = [
  ["number", "No. (low-high)"],
  ["name", "Name (A-Z)"],
  ["total", "Total stats (high-low)"],
  ["hp", "HP (high-low)"],
  ["attack", "Attack (high-low)"],
  ["speed", "Speed (high-low)"],
];

const REGIONS = ["Kanto", "Johto", "Hoenn", "Sinnoh", "Unova", "Kalos", "Alola", "Galar", "Paldea"];
const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"];

const expandedRegions = new Set([1]);

const filterState = {
  query: "",
  types: new Set(),
  typeMatch: "any",
  generation: "all",
  sort: "number",
};

function applyFilters(list) {
  let out = list;
  const q = filterState.query.trim().toLowerCase();
  if (q) {
    out = out.filter((p) => p.name.toLowerCase().includes(q) || String(p.pokedex_number).padStart(4, "0").includes(q));
  }
  if (filterState.types.size) {
    const selected = [...filterState.types];
    out = out.filter((p) => filterState.typeMatch === "all"
      ? selected.every((t) => p.types.includes(t))
      : selected.some((t) => p.types.includes(t)));
  }
  if (filterState.generation !== "all") {
    out = out.filter((p) => p.generation === Number(filterState.generation));
  }
  out = [...out];
  switch (filterState.sort) {
    case "name": out.sort((a, b) => a.name.localeCompare(b.name)); break;
    case "total": out.sort((a, b) => b.total_stats - a.total_stats); break;
    case "hp": out.sort((a, b) => b.stats.hp - a.stats.hp); break;
    case "attack": out.sort((a, b) => b.stats.attack - a.stats.attack); break;
    case "speed": out.sort((a, b) => b.stats.speed - a.stats.speed); break;
    default: out.sort((a, b) => a.pokedex_number - b.pokedex_number);
  }
  return out;
}

export async function renderPokedex(root) {
  root.textContent = "";

  const device = document.createElement("div");
  device.className = "pokedex-device";
  root.appendChild(device);

  const topRow = document.createElement("div");
  topRow.className = "pokedex-device__top";
  device.appendChild(topRow);

  const lens = document.createElement("div");
  lens.className = "pokedex-device__lens";
  lens.setAttribute("aria-hidden", "true");
  topRow.appendChild(lens);

  const titleWrap = document.createElement("div");
  titleWrap.className = "pokedex-device__title-wrap";
  titleWrap.innerHTML = `
    <h1 class="pokedex-device__title">Pokédex</h1>
    <p class="view-subtitle">Browse Pokémon by region. Select a type to filter the results.</p>`;
  topRow.appendChild(titleWrap);

  const counter = document.createElement("div");
  counter.className = "pokedex-device__counter";
  counter.setAttribute("aria-live", "polite");
  topRow.appendChild(counter);

  const progress = document.createElement("div");
  progress.className = "pokedex-device__progress";
  progress.setAttribute("role", "list");
  progress.setAttribute("aria-label", "Caught count by region");
  device.appendChild(progress);

  const screen = document.createElement("div");
  screen.className = "pokedex-device__screen";
  device.appendChild(screen);

  const toolbar = document.createElement("div");
  toolbar.className = "toolbar";
  const filters = document.createElement("section");
  filters.className = "dex-filters";
  filters.setAttribute("aria-label", "Pokédex filters");
  screen.appendChild(filters);
  filters.appendChild(toolbar);

  const genSelect = document.createElement("select");
  genSelect.className = "select";
  genSelect.style.width = "auto";
  genSelect.setAttribute("aria-label", "Filter by region");
  toolbar.appendChild(genSelect);

  const sortSelect = document.createElement("select");
  sortSelect.className = "select";
  sortSelect.style.width = "auto";
  sortSelect.setAttribute("aria-label", "Sort order");
  for (const [v, label] of SORTS) sortSelect.add(new Option(label, v));
  sortSelect.value = filterState.sort;
  toolbar.appendChild(sortSelect);

  const typeMatchSelect = document.createElement("select");
  typeMatchSelect.className = "select";
  typeMatchSelect.style.width = "auto";
  typeMatchSelect.setAttribute("aria-label", "Type matching");
  typeMatchSelect.add(new Option("Any selected type (OR)", "any"));
  typeMatchSelect.add(new Option("All selected types (AND)", "all"));
  typeMatchSelect.value = filterState.typeMatch;
  typeMatchSelect.addEventListener("change", () => {
    filterState.typeMatch = typeMatchSelect.value;
    renderGrid();
  });
  toolbar.appendChild(typeMatchSelect);

  const count = document.createElement("span");
  count.className = "toolbar__count";
  toolbar.appendChild(count);

  const typeRow = document.createElement("div");
  typeRow.className = "chip-row";
  typeRow.style.marginBottom = "1rem";
  filters.appendChild(typeRow);
  const typeHint = document.createElement("p");
  typeHint.className = "field__hint";
  typeHint.style.marginTop = ".6rem";
  typeHint.setAttribute("aria-live", "polite");
  filters.appendChild(typeHint);

  const regions = document.createElement("nav");
  regions.className = "dex-regions";
  regions.setAttribute("aria-label", "Browse Pokémon regions");
  screen.appendChild(regions);
  const regionButtons = [];
  for (const [index, label] of ["All regions", ...REGIONS].entries()) {
    const button = document.createElement("button");
    button.className = "chip-btn";
    button.textContent = label;
    const value = index === 0 ? "all" : String(index);
    button.addEventListener("click", () => {
      filterState.generation = value;
      genSelect.value = value;
      if (index) expandedRegions.add(index);
      renderGrid();
      if (index) document.getElementById(`dex-region-${index}`)?.scrollIntoView({ block: "start" });
    });
    regions.appendChild(button);
    regionButtons.push({ button, value });
  }

  const sections = document.createElement("div");
  sections.className = "dex-region-sections";
  screen.appendChild(sections);

  await ensurePokemonLoaded();

  genSelect.add(new Option("All regions", "all"));
  for (const g of state.meta.generations) genSelect.add(new Option(REGIONS[g - 1], String(g)));
  genSelect.value = filterState.generation;

  for (const t of TYPE_ORDER) {
    const btn = document.createElement("button");
    btn.className = "chip-btn" + (filterState.types.has(t) ? " is-active" : "");
    btn.textContent = t;
    btn.style.setProperty("--type-color", `var(--t-${t.toLowerCase()})`);
    btn.setAttribute("aria-pressed", filterState.types.has(t) ? "true" : "false");
    btn.addEventListener("click", () => {
      if (filterState.types.has(t)) filterState.types.delete(t);
      else filterState.types.add(t);
      btn.classList.toggle("is-active");
      btn.setAttribute("aria-pressed", filterState.types.has(t) ? "true" : "false");
      renderGrid();
    });
    typeRow.appendChild(btn);
  }

  function renderCounters() {
    const total = state.pokemon.length;
    const owned = state.collectionNumbers.size;
    const pct = total ? Math.round((owned / total) * 100) : 0;
    counter.textContent = `${String(owned).padStart(4, "0")}/${String(total).padStart(4, "0")} ${pct}%`;

    progress.textContent = "";
    for (const [index, region] of REGIONS.entries()) {
      const generation = index + 1;
      const members = state.pokemon.filter((p) => p.generation === generation);
      if (!members.length) continue;
      const ownedHere = members.filter((p) => state.collectionNumbers.has(p.pokedex_number)).length;
      const card = document.createElement("div");
      card.className = "pokedex-device__gen-card";
      card.setAttribute("role", "listitem");
      card.innerHTML = `
        <span class="pokedex-device__gen-numeral">${ROMAN[index] || generation}</span>
        <span class="pokedex-device__gen-bar"><span style="width:${members.length ? (ownedHere / members.length) * 100 : 0}%"></span></span>
        <span class="pokedex-device__gen-count">${ownedHere}/${members.length}</span>`;
      card.title = region;
      progress.appendChild(card);
    }
  }

  function renderGrid() {
    const selectedTypes = [...filterState.types];
    typeHint.textContent = !selectedTypes.length
      ? "Select one or more types. Any matches either type; All matches both types."
      : filterState.typeMatch === "any"
        ? `Showing Pokémon with ${selectedTypes.join(" or ")}.`
        : selectedTypes.length > 2
          ? "Pokémon have at most two types. Select one or two types to use All."
          : `Showing Pokémon with ${selectedTypes.join(" and ")}${selectedTypes.length === 2 ? " together (dual type)" : ""}.`;
    const results = applyFilters(state.pokemon);
    count.textContent = `${results.length.toLocaleString()} Pokémon`;
    for (const { button, value } of regionButtons) {
      const active = value === filterState.generation;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    }
    renderCounters();
    sections.textContent = "";
    if (!results.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.innerHTML = `<p class="empty-state__title">No matches</p><p>Try clearing a filter or searching a different name or number.</p>`;
      sections.appendChild(empty);
      return;
    }
    for (const [index, region] of REGIONS.entries()) {
      const generation = index + 1;
      const members = results.filter((p) => p.generation === generation);
      if (!members.length) continue;
      const section = document.createElement("details");
      section.className = "dex-region-section";
      section.id = `dex-region-${generation}`;
      section.open = expandedRegions.has(generation) || filterState.generation !== "all" || Boolean(filterState.query.trim()) || filterState.types.size > 0;
      const summary = document.createElement("summary");
      summary.className = "dex-region-heading";
      const heading = document.createElement("h2");
      heading.textContent = region;
      const subtitle = document.createElement("span");
      subtitle.textContent = `Generation ${generation} · ${members.length} Pokémon`;
      summary.append(heading, subtitle);
      section.appendChild(summary);
      const grid = document.createElement("div");
      grid.className = "dex-grid";
      section.appendChild(grid);
      let populated = false;
      function populate() {
        if (populated) return;
        populated = true;
        const fragment = document.createDocumentFragment();
        for (const p of members) {
          fragment.appendChild(specimenCard(p, { onClick: (poke) => openDetail(poke.pokedex_number, { onChanged: renderGrid }) }));
        }
        grid.appendChild(fragment);
      }
      if (section.open) populate();
      section.addEventListener("toggle", () => {
        if (section.open) { expandedRegions.add(generation); populate(); }
        else expandedRegions.delete(generation);
      });
      sections.appendChild(section);
    }
  }

  genSelect.addEventListener("change", () => { filterState.generation = genSelect.value; renderGrid(); });
  sortSelect.addEventListener("change", () => { filterState.sort = sortSelect.value; renderGrid(); });

  const searchInput = document.getElementById("global-search");
  searchInput.value = filterState.query;
  function onSearch() {
    filterState.query = searchInput.value;
    renderGrid();
  }
  searchInput.addEventListener("input", onSearch);
  root._cleanup = () => searchInput.removeEventListener("input", onSearch);

  renderGrid();
}
