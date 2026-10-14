import { imageSrc } from "../imagesrc.js";
import { typeChipsRow } from "../typecolors.js";
import { checkIcon } from "../icons.js";

export function specimenCard(p, { onClick, showOwned = true } = {}) {
  const card = document.createElement("button");
  card.type = "button";
  card.dataset.pokemonNumber = p.pokedex_number;
  card.className = "specimen-card";
  card.setAttribute("aria-label", `${p.name}, No. ${String(p.pokedex_number).padStart(4, "0")}`);

  if (showOwned && p.owned) {
    const badge = document.createElement("span");
    badge.className = "owned-badge";
    badge.title = "In your collection";
    badge.setAttribute("aria-hidden", "true");
    badge.appendChild(checkIcon());
    card.appendChild(badge);
  }

  const art = document.createElement("div");
  art.className = "specimen-card__art";
  const img = document.createElement("img");
  img.src = imageSrc(p);
  img.alt = "";
  img.loading = "lazy";
  art.appendChild(img);
  card.appendChild(art);

  const num = document.createElement("div");
  num.className = "specimen-card__num";
  num.textContent = "#" + String(p.pokedex_number).padStart(4, "0");
  card.appendChild(num);

  const name = document.createElement("div");
  name.className = "specimen-card__name";
  name.textContent = p.name;
  card.appendChild(name);

  card.appendChild(typeChipsRow(p.types));

  if (onClick) card.addEventListener("click", () => onClick(p));
  return card;
}

export function miniRow(p, { trailing } = {}) {
  const row = document.createElement("div");
  row.className = "result-card";
  row.dataset.pokemonNumber = p.pokedex_number;

  const art = document.createElement("div");
  art.className = "result-card__art";
  const img = document.createElement("img");
  img.src = imageSrc(p);
  img.alt = "";
  art.appendChild(img);
  row.appendChild(art);

  const mid = document.createElement("div");
  const name = document.createElement("div");
  name.className = "result-card__name";
  name.textContent = p.name;
  mid.appendChild(name);
  const types = typeChipsRow(p.types);
  mid.appendChild(types);
  row.appendChild(mid);

  if (trailing) {
    const t = document.createElement("div");
    if (typeof trailing === "string") t.textContent = trailing;
    else t.appendChild(trailing);
    row.appendChild(t);
  }
  return row;
}
