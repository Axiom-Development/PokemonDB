import { api } from "./api.js";

const listeners = new Set();

export const state = {
  user: undefined, // undefined = unknown yet, null = signed out
  pokemon: null, // array, cached once
  byNumber: new Map(),
  meta: null,
  collectionNumbers: new Set(),
};

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function notify() {
  for (const fn of listeners) fn();
}

export async function ensurePokemonLoaded() {
  if (state.pokemon) return state.pokemon;
  const [{ pokemon }, meta] = await Promise.all([api.get("/api/pokemon"), api.get("/api/meta")]);
  state.pokemon = pokemon;
  state.meta = meta;
  state.byNumber = new Map(pokemon.map((p) => [p.pokedex_number, p]));
  state.collectionNumbers = new Set(pokemon.filter((p) => p.owned).map((p) => p.pokedex_number));
  notify();
  return pokemon;
}

let meInFlight = null;

export async function refreshMe() {
  if (!meInFlight) {
    meInFlight = (async () => {
      try {
        const { user } = await api.get("/api/me");
        state.user = user;
      } catch {
        state.user = null;
      }
      notify();
      meInFlight = null;
    })();
  }
  return meInFlight;
}

// Views that gate on state.user must call this first: state.user starts as
// `undefined` (unknown) until the initial /api/me check from main.js
// resolves, so checking `=== null` before that finishes would wrongly
// treat a still-loading session as signed out.
export async function ensureUserResolved() {
  if (state.user === undefined) await refreshMe();
}

export async function refreshCollection() {
  if (!state.user) {
    state.collectionNumbers = new Set();
    notify();
    return;
  }
  const { pokemon } = await api.get("/api/collection");
  state.collectionNumbers = new Set(pokemon.map((p) => p.pokedex_number));
  if (state.pokemon) {
    for (const p of state.pokemon) p.owned = state.collectionNumbers.has(p.pokedex_number);
  }
  notify();
}

export function isOwned(pokedexNumber) {
  return state.collectionNumbers.has(pokedexNumber);
}

export async function signOut() {
  await api.post("/api/logout");
  state.user = null;
  state.collectionNumbers = new Set();
  if (state.pokemon) for (const p of state.pokemon) p.owned = false;
  notify();
}
