(() => {
  const root = document.documentElement;
  const system = window.matchMedia("(prefers-color-scheme: dark)");
  const storageKey = "mtg-theme";
  let selectedTheme = readPreference();
  let toggle;

  function readPreference() {
    try {
      const saved = localStorage.getItem(storageKey);
      return saved === "light" || saved === "dark" ? saved : null;
    } catch {
      return null;
    }
  }

  function renderTheme() {
    root.dataset.theme = selectedTheme ?? (system.matches ? "dark" : "light");
    if (toggle) {
      const label = root.dataset.theme === "dark" ? "Helles Design einschalten" : "Dunkles Design einschalten";
      toggle.setAttribute("aria-label", label);
      toggle.title = label;
    }
  }

  renderTheme();
  document.addEventListener("DOMContentLoaded", () => {
    toggle = document.querySelector(".theme-toggle");
    toggle.addEventListener("click", () => {
      selectedTheme = root.dataset.theme === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(storageKey, selectedTheme);
      } catch {
        // The toggle remains usable when storage is unavailable.
      }
      renderTheme();
    });
    renderTheme();
    toggle.hidden = false;
  });

  system.addEventListener("change", renderTheme);
  window.addEventListener("storage", event => {
    if (event.key === storageKey || event.key === null) {
      selectedTheme = readPreference();
      renderTheme();
    }
  });
})();
