let timer = null;

export function toast(message) {
  const root = document.getElementById("toast-root");
  root.textContent = message;
  root.classList.remove("visually-hidden");
  root.classList.add("banner", "banner-info");
  root.style.position = "fixed";
  root.style.bottom = "1.25rem";
  root.style.left = "50%";
  root.style.transform = "translateX(-50%)";
  root.style.zIndex = "40";
  clearTimeout(timer);
  timer = setTimeout(() => {
    root.classList.add("visually-hidden");
    root.removeAttribute("style");
  }, 2600);
}
