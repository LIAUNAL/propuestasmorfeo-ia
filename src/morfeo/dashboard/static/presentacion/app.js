/* Navegación de diapositivas tomada de LIAUNAL/AgentPt (https://github.com/LIAUNAL/AgentPt, commit 4d23022). Copia sin cambios. */
const slides = Array.from(document.querySelectorAll(".slide"));
const railModules = Array.from(document.querySelectorAll(".rail-module"));
const railTitles = Array.from(document.querySelectorAll(".rail-title"));
const counter = document.getElementById("counter");
const prevBtn = document.getElementById("prev");
const nextBtn = document.getElementById("next");
const deckApp = document.querySelector(".deck-app");
const modeBadge = document.getElementById("mode-badge");

let current = 0;
let cleanupTimer = null;
let lastModule = null;
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

const modeMap = {
  0: "normal",
  1: "command",
  2: "insert",
  3: "visual",
  4: "replace",
  5: "terminal",
  6: "normal",
  7: "command",
  8: "insert",
  9: "visual",
  10: "replace",
  11: "terminal"
};

function buildDots() {
  const moduleMap = {};
  slides.forEach((slide, idx) => {
    const mod = slide.dataset.module;
    if (!moduleMap[mod]) moduleMap[mod] = [];
    moduleMap[mod].push(idx);
  });

  Object.entries(moduleMap).forEach(([mod, indices]) => {
    const container = document.getElementById(`dots-${mod}`);
    if (!container) return;
    indices.forEach((slideIdx) => {
      const pip = document.createElement("button");
      pip.className = "rail-pip";
      pip.dataset.slide = slideIdx;
      pip.setAttribute("aria-label", `Slide ${slideIdx + 1}`);
      pip.addEventListener("click", () => render(slideIdx));
      container.appendChild(pip);
    });
  });
}

function pad(value) {
  return String(value).padStart(2, "0");
}

function cleanupTransitionClasses(slide) {
  slide.classList.remove(
    "is-entering",
    "is-leaving",
    "from-next",
    "from-prev",
    "to-next",
    "to-prev"
  );
}

function updateChrome() {
  const pips = Array.from(document.querySelectorAll(".rail-pip"));
  pips.forEach((pip) => {
    pip.classList.toggle("is-active", Number(pip.dataset.slide) === current);
  });

  const currentModule = slides[current]?.dataset.module;
  const moduleChanged = currentModule !== lastModule;
  railModules.forEach((mod) => {
    const isActive = mod.dataset.module === currentModule;
    mod.classList.toggle("is-active-module", isActive);
    if (isActive && moduleChanged) {
      mod.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
    }
  });
  lastModule = currentModule;

  counter.textContent = `${pad(current + 1)} / ${pad(slides.length)}`;

  prevBtn.disabled = current === 0;
  nextBtn.disabled = current === slides.length - 1;

  const tone = slides[current]?.dataset.tone;
  const moduleIdx = Number(currentModule);
  const mode = modeMap[moduleIdx] || "normal";

  deckApp.className = deckApp.className
    .replace(/tone-\w+/g, "")
    .replace(/mode-\w+/g, "")
    .replace(/\s+/g, " ")
    .trim();

  if (tone) deckApp.classList.add(`tone-${tone}`);
  deckApp.classList.add(`mode-${mode}`);

  if (modeBadge) {
    modeBadge.textContent = mode.toUpperCase();
  }
}

function render(index, options = {}) {
  const { animate = true } = options;
  const next = Math.max(0, Math.min(index, slides.length - 1));

  if (next === current) {
    updateChrome();
    return;
  }

  const previous = current;
  current = next;
  try { localStorage.setItem("deck-slide-v2", current); } catch (_) {}

  // Una pulsacion nueva cancela la transicion en curso en vez de descartarse.
  if (cleanupTimer) {
    window.clearTimeout(cleanupTimer);
    cleanupTimer = null;
  }

  const currentSlide = slides[current];
  const previousSlide = slides[previous];

  // Cualquier slide ajeno a la transicion vuelve a su estado de reposo.
  slides.forEach((slide, idx) => {
    if (idx !== current && idx !== previous) {
      cleanupTransitionClasses(slide);
      slide.classList.remove("is-active");
    }
  });

  cleanupTransitionClasses(previousSlide);
  cleanupTransitionClasses(currentSlide);

  if (!animate || reduceMotion.matches) {
    previousSlide.classList.remove("is-active");
    currentSlide.classList.add("is-active");
    updateChrome();
    return;
  }

  const direction = next > previous ? "next" : "prev";

  previousSlide.classList.remove("is-active");
  previousSlide.classList.add("is-leaving", direction === "next" ? "to-next" : "to-prev");

  currentSlide.classList.add("is-active", "is-entering", direction === "next" ? "from-next" : "from-prev");

  cleanupTimer = window.setTimeout(() => {
    slides.forEach((slide) => {
      cleanupTransitionClasses(slide);
      if (slide !== slides[current]) slide.classList.remove("is-active");
    });
    cleanupTimer = null;
  }, 440);

  updateChrome();
}

railTitles.forEach((title) => {
  title.addEventListener("click", () => {
    const firstSlide = Number(title.dataset.first);
    if (!Number.isFinite(firstSlide)) return;
    render(firstSlide);
  });
});

prevBtn.addEventListener("click", () => render(current - 1));
nextBtn.addEventListener("click", () => render(current + 1));

window.addEventListener("keydown", (event) => {
  const opts = { animate: !event.repeat };
  if (event.key === "ArrowRight" || event.key === "PageDown" || event.key === " ") {
    event.preventDefault();
    render(current + 1, opts);
  }
  if (event.key === "ArrowLeft" || event.key === "PageUp") {
    event.preventDefault();
    render(current - 1, opts);
  }
  if (event.key === "Home") render(0);
  if (event.key === "End") render(slides.length - 1);
  if (event.key.toLowerCase() === "f") {
    document.body.classList.toggle("focus-mode");
  }
});

let touchStartX = 0;
window.addEventListener("touchstart", (event) => {
  touchStartX = event.changedTouches[0].screenX;
});
window.addEventListener("touchend", (event) => {
  const touchEndX = event.changedTouches[0].screenX;
  const delta = touchEndX - touchStartX;
  if (Math.abs(delta) < 40) return;
  if (delta < 0) render(current + 1);
  if (delta > 0) render(current - 1);
});

buildDots();
const saved = Number(localStorage.getItem("deck-slide-v2")) || 0;
render(Math.min(saved, slides.length - 1), { animate: false });
