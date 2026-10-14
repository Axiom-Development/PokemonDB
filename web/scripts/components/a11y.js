// Shared focus-trap for modal dialogs (picker, detail drawer, confirm/prompt
// dialogs): keeps Tab/Shift+Tab cycling inside the container while it's open.
const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function focusableIn(container) {
  return [...container.querySelectorAll(FOCUSABLE_SELECTOR)].filter(
    (el) => el.offsetParent !== null || el === document.activeElement
  );
}

export function trapFocus(container) {
  function onKeydown(e) {
    if (e.key !== "Tab") return;
    const items = focusableIn(container);
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    } else if (!items.includes(document.activeElement)) {
      // Focus drifted outside the dialog (e.g. programmatic focus) -- pull it back in.
      e.preventDefault();
      first.focus();
    }
  }
  container.addEventListener("keydown", onKeydown);
  return () => container.removeEventListener("keydown", onKeydown);
}
