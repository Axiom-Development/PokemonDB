// Accessible replacements for window.confirm()/window.prompt() (unsupported
// in some embedding contexts, and not stylable to match the app). Both
// return a Promise, trap focus while open, close on Escape, and restore
// focus to whatever triggered them.
import { trapFocus } from "./a11y.js";

function buildShell(title) {
  const trigger = document.activeElement;
  const scrim = document.createElement("div");
  scrim.className = "scrim";
  scrim.style.zIndex = "50";

  const box = document.createElement("div");
  box.className = "panel modal-dialog";
  box.style.zIndex = "51";
  box.setAttribute("aria-modal", "true");
  const titleId = "dlg-title-" + Math.random().toString(36).slice(2, 8);
  box.setAttribute("aria-labelledby", titleId);

  const heading = document.createElement("h2");
  heading.id = titleId;
  heading.className = "section-label";
  heading.textContent = title;
  box.appendChild(heading);

  return { trigger, scrim, box };
}

export function confirmDialog({ title, message, confirmLabel = "Confirm", cancelLabel = "Cancel", danger = false }) {
  return new Promise((resolve) => {
    const { trigger, scrim, box } = buildShell(title);
    box.setAttribute("role", "alertdialog");

    const msg = document.createElement("p");
    msg.textContent = message;
    box.appendChild(msg);

    const actions = document.createElement("div");
    actions.className = "dialog-actions";
    const cancelBtn = document.createElement("button");
    cancelBtn.type = "button";
    cancelBtn.className = "btn btn-ghost";
    cancelBtn.textContent = cancelLabel;
    const confirmBtn = document.createElement("button");
    confirmBtn.type = "button";
    confirmBtn.className = danger ? "btn btn-danger" : "btn btn-primary";
    confirmBtn.textContent = confirmLabel;
    actions.append(cancelBtn, confirmBtn);
    box.appendChild(actions);

    let untrap;
    function teardown(result) {
      untrap?.();
      document.removeEventListener("keydown", onKey);
      scrim.remove();
      box.remove();
      if (trigger && trigger.focus) trigger.focus();
      resolve(result);
    }
    function onKey(e) {
      if (e.key === "Escape") teardown(false);
    }
    cancelBtn.addEventListener("click", () => teardown(false));
    confirmBtn.addEventListener("click", () => teardown(true));
    scrim.addEventListener("click", () => teardown(false));
    document.addEventListener("keydown", onKey);

    document.body.append(scrim, box);
    untrap = trapFocus(box);
    cancelBtn.focus(); // Cancel is the safe default for destructive actions.
  });
}

export function promptDialog({ title, message, label, initialValue = "", confirmLabel = "Save", cancelLabel = "Cancel", placeholder = "" }) {
  return new Promise((resolve) => {
    const { trigger, scrim, box } = buildShell(title);
    box.setAttribute("role", "dialog");

    if (message) {
      const msg = document.createElement("p");
      msg.className = "field__hint";
      msg.textContent = message;
      box.appendChild(msg);
    }

    const form = document.createElement("form");
    const field = document.createElement("div");
    field.className = "field";
    const inputId = "dlg-input-" + Math.random().toString(36).slice(2, 8);
    const fieldLabel = document.createElement("label");
    fieldLabel.className = "field__label";
    fieldLabel.htmlFor = inputId;
    fieldLabel.textContent = label;
    const input = document.createElement("input");
    input.className = "input";
    input.id = inputId;
    input.value = initialValue;
    input.placeholder = placeholder;
    input.maxLength = 40;
    field.append(fieldLabel, input);
    form.appendChild(field);

    const actions = document.createElement("div");
    actions.className = "dialog-actions";
    const cancelBtn = document.createElement("button");
    cancelBtn.type = "button";
    cancelBtn.className = "btn btn-ghost";
    cancelBtn.textContent = cancelLabel;
    const confirmBtn = document.createElement("button");
    confirmBtn.type = "submit";
    confirmBtn.className = "btn btn-primary";
    confirmBtn.textContent = confirmLabel;
    actions.append(cancelBtn, confirmBtn);
    form.appendChild(actions);
    box.appendChild(form);

    let untrap;
    function teardown(result) {
      untrap?.();
      document.removeEventListener("keydown", onKey);
      scrim.remove();
      box.remove();
      if (trigger && trigger.focus) trigger.focus();
      resolve(result);
    }
    function onKey(e) {
      if (e.key === "Escape") teardown(null);
    }
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      teardown(input.value.trim() || null);
    });
    cancelBtn.addEventListener("click", () => teardown(null));
    scrim.addEventListener("click", () => teardown(null));
    document.addEventListener("keydown", onKey);

    document.body.append(scrim, box);
    untrap = trapFocus(box);
    input.focus();
    input.select();
  });
}
