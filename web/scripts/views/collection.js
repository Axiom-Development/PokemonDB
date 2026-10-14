import { state, ensurePokemonLoaded, ensureUserResolved } from "../state.js";
import { specimenCard } from "../components/pokecard.js";
import { openDetail } from "../components/detail.js";

export async function renderCollection(root) {
  root.textContent = "";
  await ensureUserResolved();

  if (state.user === null) {
    root.innerHTML = `
      <div class="view-header"><div>
        <h1 class="view-title">My collection</h1>
      </div></div>
      <div class="empty-state">
        <p class="empty-state__title">Sign in to build a collection</p>
        <p>Your collection is tied to your account, not this browser, so it stays with you. Sign in or create an account to start adding Pokémon.</p>
      </div>`;
    root.querySelector(".empty-state").insertAdjacentHTML(
      "beforeend",
      `<p style="margin-top:1rem"><a class="btn btn-primary" href="#/account">Go to account</a></p>`
    );
    return;
  }

  const header = document.createElement("div");
  header.className = "view-header";
  header.innerHTML = `
    <div>
      <h1 class="view-title">My collection</h1>
      <p class="view-subtitle">The Pokémon you've caught, kept in your account. Collection membership drives ownership filters in Team Builder and Battle Planner.</p>
    </div>`;
  root.appendChild(header);

  const toolbar = document.createElement("div");
  toolbar.className = "toolbar";
  const search = document.createElement("input");
  search.className = "input";
  search.style.maxWidth = "20rem";
  search.type = "search";
  search.placeholder = "Search your collection…";
  const count = document.createElement("span");
  count.className = "toolbar__count";
  toolbar.append(search, count);
  root.appendChild(toolbar);

  const grid = document.createElement("div");
  grid.className = "dex-grid";
  root.appendChild(grid);

  await ensurePokemonLoaded();

  function renderGrid() {
    const q = search.value.trim().toLowerCase();
    let owned = state.pokemon.filter((p) => p.owned);
    if (q) owned = owned.filter((p) => p.name.toLowerCase().includes(q) || String(p.pokedex_number).includes(q));
    owned.sort((a, b) => a.pokedex_number - b.pokedex_number);
    count.innerHTML = `<span class="lcd-num">${owned.length.toLocaleString()}</span> caught`;
    grid.textContent = "";
    if (owned.length === 0) {
      grid.innerHTML = `<div class="empty-state">
        <p class="empty-state__title">No Pokémon yet</p>
        <p>Browse the Pokédex and add species to your collection -- they'll show up here with an owned badge everywhere in the app.</p>
        <p style="margin-top:1rem"><a class="btn btn-primary" href="#/dex">Browse the Pokédex</a></p>
      </div>`;
      return;
    }
    const frag = document.createDocumentFragment();
    for (const p of owned) {
      frag.appendChild(specimenCard(p, { onClick: (poke) => openDetail(poke.pokedex_number, { onChanged: renderGrid }) }));
    }
    grid.appendChild(frag);
  }

  search.addEventListener("input", renderGrid);
  renderGrid();
}
