// Hand-drawn inline SVG icons (24px grid, ~2px ink strokes) for the GBA
// menu skin. Only icons the app actually uses -- no icon-font, no library.
const SVG_NS = "http://www.w3.org/2000/svg";

function svg(viewBox, inner, extraClass) {
  const el = document.createElementNS(SVG_NS, "svg");
  el.setAttribute("viewBox", viewBox);
  el.setAttribute("aria-hidden", "true");
  el.setAttribute("focusable", "false");
  if (extraClass) el.setAttribute("class", extraClass);
  el.innerHTML = inner;
  return el;
}

export function pokeballIcon(extraClass) {
  return svg(
    "0 0 24 24",
    `<circle cx="12" cy="12" r="9.5" fill="#EE1515" stroke="#222224" stroke-width="2"/>
     <path d="M2.5 12h7a2.5 2.5 0 0 0 5 0h7" fill="none" stroke="#222224" stroke-width="2"/>
     <path d="M2.5 12a9.5 9.5 0 0 1 19 0" fill="#EE1515" stroke="#222224" stroke-width="2"/>
     <path d="M2.5 12a9.5 9.5 0 0 0 19 0" fill="#FFFFFF" stroke="#222224" stroke-width="2"/>
     <circle cx="12" cy="12" r="2.6" fill="#FFFFFF" stroke="#222224" stroke-width="2"/>`,
    extraClass
  );
}

export function closeIcon(extraClass) {
  return svg(
    "0 0 24 24",
    `<path d="M5 5l14 14M19 5L5 19" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/>`,
    extraClass
  );
}

export function checkIcon(extraClass) {
  return svg(
    "0 0 24 24",
    `<path d="M4 12.5l5.5 5.5L20 6.5" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>`,
    extraClass
  );
}
