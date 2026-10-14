import { state, isOwned, refreshCollection } from "../state.js";
import { api } from "../api.js";
import { openDetail } from "./detail.js";
import { toast } from "./toast.js";
import { navigateTo } from "../router.js";

export function setupContextMenu() {
  let menu = null;
  let trigger = null;
  function close(restore = false) {
    menu?.remove();
    menu = null;
    if (restore && trigger?.isConnected) trigger.focus({ preventScroll: true });
  }
  function show(event, card, keyboard = false) {
    const p = state.byNumber.get(Number(card.dataset.pokemonNumber));
    if (!p) return;
    event.preventDefault();
    close();
    trigger = card;
    menu = document.createElement("div");
    menu.className = "pokemon-context-menu";
    menu.setAttribute("role", "menu");
    menu.setAttribute("aria-label", `${p.name} actions`);
    const title = document.createElement("div");
    title.className = "pokemon-context-menu__title";
    title.textContent = p.name;
    menu.appendChild(title);
    function action(label, run) {
      const button = document.createElement("button");
      button.type = "button";
      button.setAttribute("role", "menuitem");
      button.textContent = label;
      button.addEventListener("click", async () => {
        close(true);
        try { await run(); } catch (error) { toast(error.message || "Unable to complete that action."); }
      });
      menu.appendChild(button);
    }
    action("View details", () => openDetail(p.pokedex_number));
    const owned = isOwned(p.pokedex_number);
    if (state.user) {
      action(owned ? "Remove from collection" : "Add to collection", async () => {
        if (owned) await api.del(`/api/collection/${p.pokedex_number}`);
        else await api.post("/api/collection", { pokedex_number: p.pokedex_number });
        await refreshCollection();
        toast(`${owned ? "Removed" : "Added"} ${p.name}.`);
        const route = location.hash.replace(/^#\/?/, "").split("/")[0] || "dex";
        navigateTo(route);
      });
    } else {
      action("Sign in to add to collection", () => navigateTo("account"));
    }
    action("Copy Pokémon name", async () => {
      await navigator.clipboard.writeText(p.name);
      toast("Pokémon name copied.");
    });
    document.body.appendChild(menu);
    const bounds = card.getBoundingClientRect();
    const x = keyboard ? bounds.left : event.clientX;
    const y = keyboard ? bounds.bottom : event.clientY;
    menu.style.left = `${Math.max(8, Math.min(x, innerWidth - menu.offsetWidth - 8))}px`;
    menu.style.top = `${Math.max(8, Math.min(y, innerHeight - menu.offsetHeight - 8))}px`;
    menu.querySelector("button").focus();
  }
  document.addEventListener("contextmenu", (event) => {
    const card = event.target.closest("[data-pokemon-number]");
    if (card) show(event, card, event.clientX === 0 && event.clientY === 0);
    else close();
  });
  document.addEventListener("pointerdown", (event) => {
    if (menu && !menu.contains(event.target)) close();
  });
  document.addEventListener("keydown", (event) => {
    if (!menu) {
      const card = event.target.closest("[data-pokemon-number]");
      if (card && (event.key === "ContextMenu" || (event.shiftKey && event.key === "F10"))) show(event, card, true);
      return;
    }
    if (event.key === "Escape") { event.preventDefault(); close(true); }
    else if (event.key === "Tab") close();
    else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      const items = [...menu.querySelectorAll("button")];
      let index = items.indexOf(document.activeElement);
      index = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1 : (index + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
      items[index].focus();
    }
  });
  window.addEventListener("scroll", () => close(), true);
  window.addEventListener("resize", () => close());
  window.addEventListener("hashchange", () => close());
}
