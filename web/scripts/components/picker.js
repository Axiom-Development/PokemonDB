import { imageSrc } from "../imagesrc.js";
import { state } from "../state.js";
import { typeChipsRow } from "../typecolors.js";
import { trapFocus } from "./a11y.js";
import { closeIcon } from "../icons.js";

export function openPicker({ title, exclude = new Set(), onSelect }) {
  const trigger = document.activeElement;
  const scrim = document.createElement("div");
  scrim.className = "scrim";
  scrim.style.zIndex = "30";

  const dialog = document.createElement("div");
  dialog.className = "drawer";
  dialog.style.zIndex = "31";
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-label", title);

  const head = document.createElement("div");
  head.className = "drawer__head";
  const h = document.createElement("h2");
  h.className = "drawer__name";
  h.textContent = title;
  const close = document.createElement("button");
  close.type = "button";
  close.className = "drawer__close";
  close.setAttribute("aria-label", "Close");
  close.appendChild(closeIcon());
  head.append(h, close);
  dialog.appendChild(head);

  const body = document.createElement("div");
  body.className = "drawer__body";
  const search = document.createElement("input");
  search.className = "input";
  search.type = "search";
  search.placeholder = "Search by name or number…";
  search.setAttribute("aria-label", "Search Pokémon");
  body.appendChild(search);

  const list = document.createElement("div");
  list.style.marginTop = "0.75rem";
  body.appendChild(list);
  dialog.appendChild(body);

  function render(query) {
    list.textContent = "";
    const q = query.trim().toLowerCase();
    const pool = state.pokemon.filter((p) => !exclude.has(p.pokedex_number));
    const filtered = q
      ? pool.filter((p) => p.name.toLowerCase().includes(q) || String(p.pokedex_number).includes(q))
      : pool;
    for (const p of filtered.slice(0, 60)) {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "result-card";
      row.style.width = "100%";
      row.style.cursor = "pointer";
      const art = document.createElement("div");
      art.className = "result-card__art";
      const img = document.createElement("img");
      img.src = imageSrc(p);
      img.alt = "";
      art.appendChild(img);
      row.appendChild(art);
      const mid = document.createElement("div");
      mid.style.textAlign = "left";
      const name = document.createElement("div");
      name.className = "result-card__name";
      name.textContent = `${p.name} · #${String(p.pokedex_number).padStart(4, "0")}`;
      mid.appendChild(name);
      mid.appendChild(typeChipsRow(p.types));
      row.appendChild(mid);
      row.addEventListener("click", () => {
        teardown();
        onSelect(p);
      });
      list.appendChild(row);
    }
    if (filtered.length === 0) {
      const empty = document.createElement("p");
      empty.className = "empty-state";
      empty.textContent = "No Pokémon match that search.";
      list.appendChild(empty);
    }
  }
  render("");
  search.addEventListener("input", () => render(search.value));

  let untrap;
  function onKey(e) {
    if (e.key === "Escape") teardown();
  }
  function teardown() {
    untrap?.();
    document.removeEventListener("keydown", onKey);
    scrim.remove();
    dialog.remove();
    if (trigger && trigger.focus) trigger.focus();
  }
  scrim.addEventListener("click", teardown);
  close.addEventListener("click", teardown);
  document.addEventListener("keydown", onKey);

  document.body.append(scrim, dialog);
  untrap = trapFocus(dialog);
  search.focus();
}
