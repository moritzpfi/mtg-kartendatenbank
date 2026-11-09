const dialog = document.querySelector("#card-dialog");
const content = dialog.querySelector(".dialog-content");
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)");
const cardBack = document.body.dataset.cardBack;

function imageUnavailable(image) {
  if (cardBack && image.getAttribute("src") !== cardBack) {
    image.src = cardBack;
    image.alt = "Magic: The Gathering – Kartenrückseite (kein Kartenbild verfügbar)";
  } else {
    image.closest(".artwork").classList.add("image-unavailable");
  }
}

document.addEventListener("error", function (event) {
  if (event.target.matches && event.target.matches("img.card-art")) imageUnavailable(event.target);
}, true);

document.querySelectorAll("img.card-art").forEach(function (image) {
  if (image.complete && image.naturalWidth === 0) imageUnavailable(image);
});

document.querySelectorAll(".open-card").forEach(function (button) {
  button.addEventListener("pointermove", function (event) {
    if (reducedMotion.matches || !finePointer.matches) return;
    const bounds = button.getBoundingClientRect();
    const x = (event.clientX - bounds.left) / bounds.width - .5;
    const y = (event.clientY - bounds.top) / bounds.height - .5;
    button.style.setProperty("--rx", (-y * 10) + "deg");
    button.style.setProperty("--ry", (x * 10) + "deg");
    button.style.setProperty("--mx", (x * 5) + "px");
    button.style.setProperty("--my", (y * 5) + "px");
  });
  button.addEventListener("pointerleave", function () {
    ["--rx", "--ry", "--mx", "--my"].forEach(name => button.style.removeProperty(name));
  });
  button.addEventListener("click", function () {
    content.replaceChildren(button.closest(".card").querySelector(".card-preview").content.cloneNode(true));
    dialog.showModal();
  });
});

dialog.addEventListener("click", function (event) {
  if (event.target !== dialog) return;
  const bounds = dialog.getBoundingClientRect();
  if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
});
dialog.addEventListener("close", function () { content.replaceChildren(); });
const searchForm = document.querySelector(".search");
let leavingStartPage = false;
let searchNavigation;

searchForm.addEventListener("submit", function (event) {
  if (!document.body.classList.contains("start-page") || reducedMotion.matches) return;
  event.preventDefault();
  if (leavingStartPage) return;
  leavingStartPage = true;
  searchForm.setAttribute("aria-busy", "true");
  document.body.classList.add("is-searching");
  searchNavigation = window.setTimeout(() => HTMLFormElement.prototype.submit.call(searchForm), 320);
});

document.querySelectorAll(".search-examples a").forEach(function (link) {
  link.addEventListener("click", function (event) {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    searchForm.elements.q.value = new URL(link.href).searchParams.get("q");
    searchForm.requestSubmit();
  });
});

window.addEventListener("pageshow", function (event) {
  if (!event.persisted) return;
  window.clearTimeout(searchNavigation);
  leavingStartPage = false;
  document.body.classList.remove("is-searching");
  searchForm.removeAttribute("aria-busy");
});
window.addEventListener("pagehide", () => window.clearTimeout(searchNavigation));

const detailCache = new Map();
const labels = {
  id: "Karten-ID", multiverseid: "Multiverse-ID", name: "Name", manaCost: "Manakosten",
  cmc: "Manawert", colors: "Farben", colorIdentity: "Farbidentität", type: "Kartentyp",
  types: "Typen", subtypes: "Untertypen", supertypes: "Obertypen", rarity: "Seltenheit",
  set: "Edition", setName: "Name der Edition", text: "Kartentext", flavor: "Anekdotentext",
  artist: "Künstler", number: "Sammlernummer", power: "Stärke", toughness: "Widerstandskraft",
  loyalty: "Loyalität", layout: "Layout", imageUrl: "Bild-URL", foreignNames: "Andere Sprachen",
  language: "Sprache", legalities: "Legalitäten", format: "Format", legality: "Status",
  originalText: "Originaltext", originalType: "Originaltyp", printings: "Editionen",
  variations: "Varianten", rulings: "Regelhinweise", date: "Datum", releaseDate: "Veröffentlichung"
};

function renderValue(value) {
  if (Array.isArray(value) && value.some(item => item !== null && typeof item === "object")) {
    const list = document.createElement("ul");
    value.forEach(item => {
      const entry = document.createElement("li");
      entry.append(renderValue(item));
      list.append(entry);
    });
    return list;
  }
  if (value !== null && !Array.isArray(value) && typeof value === "object") {
    const list = document.createElement("dl");
    Object.entries(value).forEach(([key, item]) => {
      const term = document.createElement("dt");
      term.textContent = Object.prototype.hasOwnProperty.call(labels, key) ? labels[key] : key;
      const description = document.createElement("dd");
      const nested = item !== null && typeof item === "object" &&
        (!Array.isArray(item) || item.some(entry => entry !== null && typeof entry === "object"));
      if (nested) {
        const section = document.createElement("details");
        const heading = document.createElement("summary");
        heading.textContent = Array.isArray(item) ? item.length + " Einträge" : "Details";
        section.append(heading, renderValue(item));
        description.append(section);
      } else {
        description.append(renderValue(item));
      }
      list.append(term, description);
    });
    return list;
  }
  const text = document.createElement("span");
  if (Array.isArray(value)) {
    text.textContent = value.map(item => item === null ? "—" : String(item)).join(", ") || "—";
  } else if (value === null || value === "") {
    text.textContent = "—";
  } else if (typeof value === "boolean") {
    text.textContent = value ? "Ja" : "Nein";
  } else {
    text.textContent = String(value);
  }
  return text;
}

async function loadDetails(details) {
  if (!details.open || details.dataset.status === "loaded" || details.dataset.status === "loading") return;
  const target = details.querySelector(".api-data");
  const id = details.dataset.cardId;
  details.dataset.status = "loading";
  target.setAttribute("aria-busy", "true");
  target.textContent = "Kartendaten werden geladen …";
  try {
    if (!detailCache.has(id)) {
      detailCache.set(id, fetch("/cards/" + encodeURIComponent(id)).then(async response => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.message || "Kartendaten konnten nicht geladen werden.");
        return data.card;
      }).catch(error => { detailCache.delete(id); throw error; }));
    }
    target.replaceChildren(renderValue(await detailCache.get(id)));
    details.dataset.status = "loaded";
  } catch (error) {
    target.textContent = error.message;
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "retry-details";
    retry.textContent = "Erneut versuchen";
    details.dataset.status = "error";
    retry.addEventListener("click", () => loadDetails(details));
    target.append(retry);
  } finally {
    target.removeAttribute("aria-busy");
  }
}

document.addEventListener("toggle", function (event) {
  if (event.target.matches("details[data-card-id]")) loadDetails(event.target);
}, true);
