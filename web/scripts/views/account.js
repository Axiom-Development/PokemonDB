import { api } from "../api.js";
import { state, refreshMe, refreshCollection, ensureUserResolved, signOut } from "../state.js";
import { toast } from "../components/toast.js";
import { navigateTo } from "../router.js";

let mode = "login"; // or "register"

function authForm(root) {
  root.innerHTML = "";
  const wrap = document.createElement("div");
  wrap.className = "auth-wrap";
  const panel = document.createElement("div");
  panel.className = "panel";

  const title = document.createElement("h1");
  title.className = "view-title";
  title.style.marginBottom = "0.3rem";
  title.textContent = mode === "login" ? "Sign in" : "Create your trainer account";
  panel.appendChild(title);

  const sub = document.createElement("p");
  sub.className = "view-subtitle";
  sub.style.marginBottom = "1.25rem";
  sub.textContent = mode === "login"
    ? "Your collection and teams are stored on this account."
    : "Pick a username and password -- stored locally, hashed, never sent anywhere else.";
  panel.appendChild(sub);

  const banner = document.createElement("div");
  panel.appendChild(banner);

  const form = document.createElement("form");
  form.noValidate = true;

  form.innerHTML = `
    <div class="field">
      <label class="field__label" for="f-username">Username</label>
      <input class="input" id="f-username" name="username" autocomplete="username" required minlength="3" maxlength="24">
      <p class="field__error" id="e-username" hidden></p>
    </div>
    <div class="field">
      <label class="field__label" for="f-password">Password</label>
      <input class="input" id="f-password" name="password" type="password"
             autocomplete="${mode === "login" ? "current-password" : "new-password"}" required minlength="8">
      <p class="field__hint">At least 8 characters.</p>
      <p class="field__error" id="e-password" hidden></p>
    </div>
    <button class="btn btn-primary btn-block" type="submit">${mode === "login" ? "Sign in" : "Create account"}</button>
  `;
  panel.appendChild(form);

  const switchP = document.createElement("p");
  switchP.className = "auth-switch";
  switchP.append(mode === "login" ? "New here? " : "Already have an account? ");
  const switchBtn = document.createElement("button");
  switchBtn.type = "button";
  switchBtn.className = "link-btn";
  switchBtn.textContent = mode === "login" ? "Create an account" : "Sign in";
  switchBtn.addEventListener("click", () => {
    mode = mode === "login" ? "register" : "login";
    authForm(root);
  });
  switchP.appendChild(switchBtn);
  panel.appendChild(switchP);

  wrap.appendChild(panel);
  root.appendChild(wrap);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    banner.textContent = "";
    banner.className = "";
    document.getElementById("e-username").hidden = true;
    document.getElementById("e-password").hidden = true;
    const username = form.username.value.trim();
    const password = form.password.value;
    try {
      if (mode === "login") await api.post("/api/login", { username, password });
      else await api.post("/api/register", { username, password });
      await refreshMe();
      await refreshCollection();
      toast(mode === "login" ? "Welcome back." : "Account created.");
      navigateTo("account");
    } catch (err) {
      if (err.field) {
        const el = document.getElementById("e-" + err.field);
        if (el) { el.textContent = err.message; el.hidden = false; }
      } else {
        banner.className = "banner banner-error";
        banner.textContent = err.message;
      }
    }
  });
}

async function dashboard(root) {
  root.innerHTML = "";
  const header = document.createElement("div");
  header.className = "view-header";
  header.innerHTML = `<div>
    <h1 class="view-title">Account</h1>
    <p class="view-subtitle">Signed in as <strong>${state.user.username}</strong>.</p>
  </div>`;
  const signOutBtn = document.createElement("button");
  signOutBtn.className = "btn btn-ghost";
  signOutBtn.textContent = "Sign out";
  signOutBtn.addEventListener("click", async () => {
    await signOut();
    toast("Signed out.");
    navigateTo("account");
  });
  header.appendChild(signOutBtn);
  root.appendChild(header);

  const grid = document.createElement("div");
  grid.className = "team-grid";
  grid.style.gridTemplateColumns = "repeat(2, 1fr)";
  root.appendChild(grid);

  let collectionCount = 0;
  let teamCount = 0;
  try {
    const [{ pokemon }, { teams }] = await Promise.all([api.get("/api/collection"), api.get("/api/teams")]);
    collectionCount = pokemon.length;
    teamCount = teams.length;
  } catch { /* leave zeros */ }

  grid.innerHTML = `
    <div class="panel account-stat">
      <p class="sc-label">Collection</p>
      <p class="account-stat__count lcd-num">${collectionCount}</p>
      <a class="btn btn-ghost btn-sm" href="#/collection">View collection</a>
    </div>
    <div class="panel account-stat">
      <p class="sc-label">Saved teams</p>
      <p class="account-stat__count lcd-num">${teamCount}</p>
      <a class="btn btn-ghost btn-sm" href="#/teams">View teams</a>
    </div>`;

  const note = document.createElement("div");
  note.className = "banner banner-amber";
  note.style.marginTop = "1.5rem";
  note.textContent = "Your account, collection and teams are saved on this computer. Password recovery is not available; if you forget your password, you can create another account.";
  root.appendChild(note);
}

export async function renderAccount(root) {
  await ensureUserResolved();
  if (state.user) await dashboard(root);
  else authForm(root);
}
