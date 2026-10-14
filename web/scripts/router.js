import { renderPokedex } from "./views/pokedex.js";
import { renderCollection } from "./views/collection.js";
import { renderTeams } from "./views/teams.js";
import { renderBattle } from "./views/battle.js";
import { renderAccount } from "./views/account.js";

const ROUTES = {
  dex: renderPokedex,
  collection: renderCollection,
  teams: renderTeams,
  battle: renderBattle,
  account: renderAccount,
};

const view = document.getElementById("view");
let rendering = 0;

function currentRoute() {
  const hash = location.hash.replace(/^#\/?/, "");
  const route = hash.split("/")[0];
  return ROUTES[route] ? route : "dex";
}

function setActiveLinks(route) {
  document.querySelectorAll("[data-route]").forEach((el) => {
    el.classList.toggle("is-active", el.dataset.route === route);
    if (el.classList.contains("rail__link")) {
      if (el.dataset.route === route) el.setAttribute("aria-current", "page");
      else el.removeAttribute("aria-current");
    }
  });
}

async function render() {
  const route = currentRoute();
  setActiveLinks(route);
  document.getElementById("global-search").style.display = route === "dex" ? "" : "none";
  if (typeof view._cleanup === "function") view._cleanup();
  const token = ++rendering;
  try {
    await ROUTES[route](view);
  } catch (err) {
    if (token !== rendering) return;
    view.innerHTML = `<div class="banner banner-error">Something went wrong loading this page: ${err.message}</div>`;
    console.error(err);
  }
  if (token !== rendering) return;
  // Reset scroll to the top deliberately on every route change -- relying
  // on focus()'s default scroll-into-view left the new heading partially
  // scrolled out of view when the previous view had been scrolled down.
  // preventScroll keeps focus() from fighting this. #view is its own
  // scroll container (the topbar sits outside it), so reset its scrollTop
  // directly rather than the window's.
  view.scrollTop = 0;
  view.focus({ preventScroll: true });
}

export function navigateTo(route) {
  if (currentRoute() === route) render();
  else location.hash = "#/" + route;
}

export function startRouter() {
  window.addEventListener("hashchange", render);
  render();
}
