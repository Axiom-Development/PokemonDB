import { inject } from 'https://cdn.jsdelivr.net/npm/@vercel/analytics@2/dist/index.mjs';
import { injectSpeedInsights } from 'https://cdn.jsdelivr.net/npm/@vercel/speed-insights@1/dist/index.mjs';
import { setupContextMenu } from "./components/contextmenu.js";
import { state, subscribe, refreshMe, refreshCollection } from "./state.js";
import { startRouter } from "./router.js";

// Initialize Vercel Web Analytics
inject();

// Initialize Vercel Speed Insights
injectSpeedInsights();

function renderTopbarAccount() {
  const mount = document.getElementById("topbar-account");
  mount.textContent = "";
  if (state.user === undefined) return;
  if (state.user === null) {
    const link = document.createElement("a");
    link.className = "btn btn-primary btn-sm";
    link.href = "#/account";
    link.textContent = "Sign in";
    mount.appendChild(link);
    return;
  }
  const name = document.createElement("span");
  name.textContent = state.user.username;
  name.style.fontWeight = "600";
  mount.appendChild(name);
  const link = document.createElement("a");
  link.className = "btn btn-ghost btn-sm";
  link.href = "#/account";
  link.textContent = "Account";
  mount.appendChild(link);
}

subscribe(renderTopbarAccount);

async function boot() {
  startRouter();
  await refreshMe();
  await refreshCollection();
}

boot();

setupContextMenu();
