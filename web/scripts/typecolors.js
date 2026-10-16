// Display-only color mapping for the 18 types. The actual type chart and
// every score/weakness calculation lives server-side in app/types.py and
// app/battle.py -- this file only decides how a type name is painted.
export const TYPE_ORDER = [
  "Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting",
  "Poison", "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost",
  "Dragon", "Dark", "Steel", "Fairy",
];

const VAR = (name) => `var(--t-${name.toLowerCase()})`;

// Types whose official fill colour is dark enough to need white label text;
// everything else sits on ink text. Picked by relative luminance against
// the fixed type palette in styles/tokens.css -- update both together.
// (Psychic #F85888 is light: ink text is 5.1:1, white only 3.1:1.)
const WHITE_TEXT_TYPES = new Set(["Fighting", "Poison", "Ghost", "Dragon", "Dark"]);

export function typeChip(type, { selected = false } = {}) {
  const dot = VAR(type);
  const span = document.createElement("span");
  span.className = "type-chip" + (selected ? " is-selected" : "");
  span.style.setProperty("--dot", dot);
  span.style.setProperty("--tint", `color-mix(in srgb, ${dot} 16%, var(--bezel))`);
  span.style.setProperty("--chip-ink", WHITE_TEXT_TYPES.has(type) ? "var(--white)" : "var(--ink)");
  const d = document.createElement("span");
  d.className = "type-chip__dot";
  span.appendChild(d);
  span.append(type);
  return span;
}

export function typeChipsRow(types) {
  const row = document.createElement("div");
  row.className = "specimen-card__types";
  for (const t of types) row.appendChild(typeChip(t));
  return row;
}
