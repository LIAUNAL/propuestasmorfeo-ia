/**
 * Arnés DOM para el visor PDF continuo del tablero
 * (`src/morfeo/dashboard/static/index.html`).
 *
 * El visor es JavaScript en línea dentro de un único HTML, y hoy solo está
 * fijado por aserciones de cadena, que no pueden observar comportamiento. Este
 * arnés extrae ese guion en línea, lo ejecuta tal cual bajo jsdom y deja
 * controlar el tiempo de las promesas para suspender un render exactamente
 * donde la prueba lo necesite.
 *
 * Frontera del doblez: solo se doblan navegador y PDF.js (pdfjsLib,
 * IntersectionObserver, canvas y su contexto 2D, requestAnimationFrame, fetch,
 * temporizadores y geometría). Ninguna función del visor se reimplementa ni se
 * sustituye: el código bajo prueba es el archivo real, extraído en cada corrida.
 *
 * Prerrequisito: jsdom. Un checkout nuevo necesita `npm install` (o `npm ci`) en
 * la raíz antes de `npm test`; la suite de Python no depende de eso, porque
 * `tests/test_dashboard_viewer_dom.py` se salta cuando jsdom no está.
 *
 * Límite declarado: jsdom no trae motor de render ni de layout. Lo observable
 * aquí es el flujo asíncrono, el estado del DOM que el visor escribe (canvas,
 * capa de texto, registro de páginas pintadas) y el orden de las operaciones.
 * No es observable la pintura real de píxeles ni el pipeline interno de PDF.js:
 * el doblez de `page.render()` resuelve la promesa, no pinta.
 */

import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { JSDOM } from 'jsdom';

const HERE = path.dirname(fileURLToPath(import.meta.url));

export const REPO_ROOT = path.resolve(HERE, '..', '..');
// El visor bajo prueba es siempre el archivo del árbol, salvo que la corrida
// apunte a una copia explícita. Eso permite verificar la suite contra el
// `index.html` original en una copia de trabajo temporal, sin tocar el árbol.
export const DASHBOARD_INDEX = process.env.VIEWER_INDEX_PATH
  ? path.resolve(process.env.VIEWER_INDEX_PATH)
  : path.join(
      REPO_ROOT,
      'src',
      'morfeo',
      'dashboard',
      'static',
      'index.html',
    );

const SCRIPT_TAG = /<script\b([^>]*)>([\s\S]*?)<\/script>/gi;

/** Único `<script>` en línea del tablero, con su código tal como está en disco. */
export function extractInlineScript(html) {
  const inline = [];
  for (const match of html.matchAll(SCRIPT_TAG)) {
    const attrs = match[1] || '';
    if (/\bsrc\s*=/i.test(attrs)) continue;
    inline.push(match[2] || '');
  }
  if (inline.length !== 1) {
    throw new Error(
      `index.html debería tener exactamente un <script> en línea; encontré ${inline.length}`,
    );
  }
  return inline[0];
}

/** Promesa que solo se asienta cuando alguien lo pide. */
function deferred() {
  let settleWith;
  let settled = false;
  const promise = new Promise((resolve, reject) => {
    settleWith = { resolve, reject };
  });
  const settle = (fn, value) => {
    if (settled) return false;
    settled = true;
    fn(value);
    return true;
  };
  return {
    promise,
    resolve: (value) => settle(settleWith.resolve, value),
    reject: (error) => settle(settleWith.reject, error),
    get settled() {
      return settled;
    },
  };
}

/** Deja correr microtareas. `setImmediate` corre después de vaciar su cola. */
export function flush(rounds = 4) {
  let chain = Promise.resolve();
  for (let i = 0; i < rounds; i += 1) {
    chain = chain.then(() => new Promise((resolve) => setImmediate(resolve)));
  }
  return chain;
}

// --- Reloj manual ---------------------------------------------------------
// Nada de temporizadores reales: el visor usa debounces, rAF y prefetch con
// retardo, y dejarlos correr solos volvería la prueba dependiente del azar.
function createClock() {
  let now = 0;
  let seq = 0;
  const timers = new Map();

  const schedule = (kind, fn, delay, args) => {
    seq += 1;
    timers.set(seq, {
      kind,
      fn,
      args,
      time: now + Math.max(0, Number(delay) || 0),
      interval: kind === 'interval' ? Math.max(1, Number(delay) || 1) : null,
    });
    return seq;
  };

  return {
    install(window) {
      window.setTimeout = (fn, delay, ...args) => schedule('timeout', fn, delay, args);
      window.clearTimeout = (id) => timers.delete(id);
      window.setInterval = (fn, delay, ...args) => schedule('interval', fn, delay, args);
      window.clearInterval = (id) => timers.delete(id);
      window.requestAnimationFrame = (fn) => schedule('raf', fn, 0, [now]);
      window.cancelAnimationFrame = (id) => timers.delete(id);
    },
    pending: () => timers.size,
    /** Corre lo que venza hasta `ms` desde ahora, en orden de vencimiento. */
    async advance(ms = 0) {
      const target = now + ms;
      for (let guard = 0; guard < 10_000; guard += 1) {
        let nextId = null;
        for (const [id, timer] of timers) {
          if (timer.time > target) continue;
          if (nextId === null || timer.time < timers.get(nextId).time) nextId = id;
        }
        if (nextId === null) break;
        const timer = timers.get(nextId);
        now = Math.max(now, timer.time);
        if (timer.interval === null) timers.delete(nextId);
        else timer.time = now + timer.interval;
        timer.fn(...timer.args);
        await flush(1);
      }
      now = target;
    },
    reset() {
      timers.clear();
    },
  };
}

// --- Frontera de PDF.js ---------------------------------------------------
// Tamaño de página del documento doblado: 612x792 puntos (carta) y escala 1.25
// en la carga inicial, igual que el visor real.
export const PAGE_WIDTH = 612;
export const PAGE_HEIGHT = 792;
const LAYOUT = {
  width: Math.floor(PAGE_WIDTH * 1.25),
  height: Math.floor(PAGE_HEIGHT * 1.25),
};

function cancellationError() {
  const error = new Error('Rendering cancelled');
  error.name = 'RenderingCancelledException';
  return error;
}

function createBoundary(options) {
  const numPages = options.numPages || 8;
  const documents = [];
  const documentRequests = [];
  const getPageRequests = [];
  const renders = [];
  const fetchCalls = [];
  const observers = [];
  // Cada "hold" es un cajón que aparca las tareas que llegan mientras exista.
  // Liberarlo suelta lo aparcado y además lo retira: una tarea posterior de la
  // misma página corre sola, que es lo que deja cerrar una ventana de carrera
  // sin dejar colgada la repetición de la tira.
  const getPageHolds = new Map();
  const renderHolds = new Map();
  const textContentHolds = new Map();
  const textKey = (documentIndex, pageNumber) => `${documentIndex}:${pageNumber}`;

  const ensureHold = (holds, key) => {
    if (!holds.has(key)) holds.set(key, new Set());
    return holds.get(key);
  };
  const park = (holds, key, release) => ensureHold(holds, key).add(release);
  const releaseAll = (holds, key) => {
    const bucket = holds.get(key);
    if (!bucket) return 0;
    const parked = [...bucket];
    // Liberar también retira el cajón: las tareas que ya estaban aparcadas se
    // sueltan, y una tarea posterior de la misma página vuelve a correr sola.
    holds.delete(key);
    parked.forEach((release) => release());
    return parked.length;
  };

  class FakePage {
    constructor(documentIndex, pageNumber) {
      this.documentIndex = documentIndex;
      this.pageNumber = pageNumber;
    }

    getViewport({ scale }) {
      const value = Number(scale) || 1;
      return {
        width: PAGE_WIDTH * value,
        height: PAGE_HEIGHT * value,
        scale: value,
        rotation: 0,
        transform: [value, 0, 0, -value, 0, PAGE_HEIGHT * value],
      };
    }

    getTextContent() {
      const payload = {
        items: [{ str: `Doc${this.documentIndex + 1} Página ${this.pageNumber}`, dir: 'ltr', width: 40, height: 10 }],
        styles: {},
      };
      // El cajón lleva la identidad del documento: la lectura tardía del
      // documento viejo se aparca sin bloquear la del documento nuevo.
      const key = textKey(this.documentIndex, this.pageNumber);
      if (!textContentHolds.has(key)) {
        return Promise.resolve(payload);
      }
      const settle = deferred();
      park(textContentHolds, key, () => settle.resolve(payload));
      return settle.promise;
    }

    render(params) {
      const settle = deferred();
      const record = {
        page: this.pageNumber,
        documentIndex: this.documentIndex,
        canvasContext: params ? params.canvasContext : null,
        held: false,
        cancelled: false,
        completed: false,
      };
      const release_ = () => {
        if (settle.settled) return;
        record.completed = true;
        settle.resolve();
      };
      const task = {
        promise: settle.promise,
        cancel: () => {
          if (record.cancelled) return;
          record.cancelled = true;
          // PDF.js rechaza la promesa del render al cancelar, y el rechazo
          // llega de forma asíncrona, no en la misma pila de la llamada.
          queueMicrotask(() => settle.reject(cancellationError()));
        },
        record,
      };
      record.task = task;
      renders.push(record);

      if (renderHolds.has(this.pageNumber)) {
        record.held = true;
        park(renderHolds, this.pageNumber, release_);
      } else {
        queueMicrotask(release_);
      }
      return task;
    }
  }

  class FakeDocument {
    constructor(index) {
      this.index = index;
      this.numPages = numPages;
      this.pages = new Map();
    }

    pageStub(pageNumber) {
      if (!this.pages.has(pageNumber)) {
        this.pages.set(pageNumber, new FakePage(this.index, pageNumber));
      }
      return this.pages.get(pageNumber);
    }

    getPage(pageNumber) {
      getPageRequests.push({ documentIndex: this.index, page: pageNumber });
      if (!getPageHolds.has(pageNumber)) {
        return Promise.resolve(this.pageStub(pageNumber));
      }
      const settle = deferred();
      park(getPageHolds, pageNumber, () => settle.resolve());
      return settle.promise.then(() => this.pageStub(pageNumber));
    }
  }

  const pdfjsLib = {
    GlobalWorkerOptions: {},
    getDocument(request) {
      const index = documents.length;
      const document_ = new FakeDocument(index);
      const settle = deferred();
      documents.push(document_);
      documentRequests.push({ index, url: request ? request.url : undefined });
      queueMicrotask(() => settle.resolve(document_));
      return {
        promise: settle.promise,
        onProgress: null,
        destroy: () => Promise.resolve(),
      };
    },
    renderTextLayer(params) {
      const settle = deferred();
      queueMicrotask(() => {
        const container = params ? params.container : null;
        if (container && container.ownerDocument) {
          const doc = container.ownerDocument;
          const items = (params.textContentSource && params.textContentSource.items) || [];
          const texts = items.length > 0 ? items.map((item) => item.str) : ['texto'];
          texts.forEach((text) => {
            const span = doc.createElement('span');
            span.textContent = text;
            container.appendChild(span);
          });
        }
        settle.resolve({});
      });
      return { promise: settle.promise, cancel: () => {} };
    },
  };

  return {
    pdfjsLib,
    observers,
    fetchCalls,
    clock: null,
    documentRequests,
    getPageRequests,
    renders,
    // Declarar el hold antes de arrancar el render es lo que lo aparca: el
    // doblez decide en la llamada, no después.
    holdGetPage: (pageNumber) => ensureHold(getPageHolds, pageNumber),
    releaseGetPage: (pageNumber) => releaseAll(getPageHolds, pageNumber),
    holdRender: (pageNumber) => ensureHold(renderHolds, pageNumber),
    releaseRender: (pageNumber) => releaseAll(renderHolds, pageNumber),
    holdTextContent: (pageNumber, documentIndex = 0) =>
      ensureHold(textContentHolds, textKey(documentIndex, pageNumber)),
    releaseTextContent: (pageNumber, documentIndex = 0) =>
      releaseAll(textContentHolds, textKey(documentIndex, pageNumber)),
  };
}

// --- Frontera del navegador ----------------------------------------------
function makeRect(top, left, width, height) {
  return {
    top,
    left,
    width,
    height,
    right: left + width,
    bottom: top + height,
    x: left,
    y: top,
  };
}

function pageNumberFromId(elementId) {
  const match =
    /^pdfPageSlot-(\d+)$/.exec(elementId) ||
    /^pdfPageContainer-(\d+)$/.exec(elementId) ||
    /^pdfCanvas-(\d+)$/.exec(elementId) ||
    /^pdfTextLayer-(\d+)$/.exec(elementId) ||
    /^pdfAnnotationsLayer-(\d+)$/.exec(elementId);
  return match ? Number(match[1]) : null;
}

function createContext2d(canvas) {
  return {
    canvas,
    save() {},
    restore() {},
    scale() {},
    translate() {},
    rotate() {},
    setTransform() {},
    transform() {},
    beginPath() {},
    closePath() {},
    moveTo() {},
    lineTo() {},
    rect() {},
    fill() {},
    stroke() {},
    clip() {},
    clearRect() {},
    fillRect() {},
    strokeRect() {},
    drawImage() {},
    fillText() {},
    strokeText() {},
    measureText: (text) => ({ width: String(text || '').length * 6 }),
    createLinearGradient: () => ({ addColorStop() {} }),
    getImageData: () => ({ data: new Uint8ClampedArray(4), width: 1, height: 1 }),
    putImageData() {},
  };
}

export class ViewerHarness {
  constructor(dom, boundary, code) {
    this.dom = dom;
    this.window = dom.window;
    this.document = dom.window.document;
    this.boundary = boundary;
    this.inlineScript = code;
    this.observers = boundary.observers;
  }

  /** Llama una función global del visor sin reimplementarla. */
  viewer(functionName, ...args) {
    const fn = this.window[functionName];
    if (typeof fn !== 'function') {
      throw new Error(`El visor no expone la función ${functionName}`);
    }
    return fn(...args);
  }

  /** Estado del cierre del visor, leído con eval en su ámbito global real. */
  state() {
    const raw = this.window.eval(`JSON.stringify({
      generation: pdfRenderGeneration,
      totalPages: pdfTotalPages,
      hasDocument: pdfDoc !== null,
      currentPage: pdfCurrentPage,
      scale: pdfScale,
      rendered: Array.from(pdfRenderedPages),
      pending: Array.from(pdfPendingRenders.keys()),
      renderTasks: Array.from(pdfRenderTasks.keys()),
      pageCache: Array.from(pdfPageCache.keys()),
      textCache: Array.from(pdfTextContentCache.keys())
    })`);
    return JSON.parse(raw);
  }

  hasRendered(pageNumber) {
    return this.window.eval(`pdfRenderedPages.has(${Number(pageNumber)})`);
  }

  renderRecords() {
    return this.boundary.renders;
  }

  documentRequests() {
    return this.boundary.documentRequests;
  }

  getPageRequests() {
    return this.boundary.getPageRequests;
  }

  fetchCalls() {
    return this.boundary.fetchCalls;
  }

  /** Lo observable en el DOM para una página: canvas y capa de texto vivos. */
  painted(pageNumber) {
    const canvas = this.document.getElementById(`pdfCanvas-${pageNumber}`);
    const textLayer = this.document.getElementById(`pdfTextLayer-${pageNumber}`);
    const slot = this.document.getElementById(`pdfPageSlot-${pageNumber}`);
    return {
      canvasWidth: canvas ? canvas.width : 0,
      canvasHeight: canvas ? canvas.height : 0,
      textSpans: textLayer ? textLayer.querySelectorAll('span').length : 0,
      hasLiveCanvas: Boolean(canvas),
      hasLiveSlot: Boolean(slot && slot.parentElement),
    };
  }

  isPainted(pageNumber) {
    const paint = this.painted(pageNumber);
    return paint.canvasWidth > 0 && paint.canvasHeight > 0 && paint.textSpans > 0;
  }

  slots() {
    return [...this.document.querySelectorAll('.pdf-page-slot')].map((slot) =>
      Number(slot.dataset.pageNumber),
    );
  }

  /** Dispara una intersección determinista sobre el slot vivo de esa página. */
  intersect(pageNumber) {
    const observer = this.fireIntersection(pageNumber);
    if (!observer) {
      throw new Error(`Ningún IntersectionObserver observa el slot de la página ${pageNumber}`);
    }
  }

  /**
   * Igual que `intersect`, pero devuelve `false` en lugar de lanzar cuando no
   * hay observer vivo sobre esa página. Es lo que permite observar el sello de
   * la recarga: con el observer desconectado, una intersección tardía no
   * arranca nada y la prueba lo distingue de un fallo del arnés.
   */
  tryIntersect(pageNumber) {
    return this.fireIntersection(pageNumber) ? true : false;
  }

  fireIntersection(pageNumber) {
    const slot = this.document.getElementById(`pdfPageSlot-${pageNumber}`);
    if (!slot) return null;
    const observer = [...this.observers]
      .reverse()
      .find((candidate) => candidate.targets.has(slot));
    if (!observer) return null;
    const rect = slot.getBoundingClientRect();
    observer.callback(
      [
        {
          target: slot,
          isIntersecting: true,
          intersectionRatio: 1,
          boundingClientRect: rect,
          intersectionRect: rect,
          rootBounds: null,
          time: 0,
        },
      ],
      observer,
    );
    return observer;
  }

  /** Texto que el visor dejó en la capa de texto de una página. */
  textLayerText(pageNumber) {
    const layer = this.document.getElementById(`pdfTextLayer-${pageNumber}`);
    return layer ? layer.textContent : '';
  }

  advance(ms) {
    return this.boundary.clock.advance(ms);
  }

  pendingTimers() {
    return this.boundary.clock.pending();
  }

  /** Cierra la ventana para no dejar nada colgando del proceso. */
  dispose() {
    this.window.close();
  }
}

/** Arranca un visor real bajo jsdom con la frontera doblada. */
export async function createViewerHarness(options = {}) {
  const html = await readFile(DASHBOARD_INDEX, 'utf8');
  const code = extractInlineScript(html);
  const boundary = createBoundary(options);
  const clock = createClock();
  boundary.clock = clock;

  const dom = new JSDOM(html, {
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    url: 'http://localhost:8000/',
    beforeParse(window) {
      clock.install(window);
      window.pdfjsLib = boundary.pdfjsLib;

      window.IntersectionObserver = class IntersectionObserverDouble {
        constructor(callback, observerOptions) {
          this.callback = callback;
          this.options = observerOptions;
          this.targets = new Set();
          this.disconnected = false;
          boundary.observers.push(this);
        }

        observe(target) {
          this.targets.add(target);
        }

        unobserve(target) {
          this.targets.delete(target);
        }

        disconnect() {
          this.disconnected = true;
          this.targets.clear();
        }

        takeRecords() {
          return [];
        }
      };

      window.fetch = (url, init) => {
        boundary.fetchCalls.push({
          url: String(url),
          method: (init && init.method) || 'GET',
        });
        return Promise.resolve({
          ok: false,
          status: 503,
          json: () => Promise.resolve({}),
          text: () => Promise.resolve(''),
        });
      };

      // jsdom no trae canvas ni layout: se doblan ambos, que son frontera de
      // navegador, no lógica del visor.
      window.HTMLCanvasElement.prototype.getContext = function getContext() {
        return createContext2d(this);
      };

      window.Element.prototype.getBoundingClientRect = function getBoundingClientRect() {
        const pageNumber = pageNumberFromId(this.id);
        if (pageNumber !== null) {
          return makeRect((pageNumber - 1) * (LAYOUT.height + 12), 0, LAYOUT.width, LAYOUT.height);
        }
        if (this.id === 'pdfPagesStrip' || this.id === 'pdfViewportContainer') {
          return makeRect(0, 0, LAYOUT.width, LAYOUT.height * 3);
        }
        return makeRect(0, 0, 0, 0);
      };
      window.Element.prototype.scrollTo = function scrollTo() {};
      window.Element.prototype.scrollIntoView = function scrollIntoView() {};
      window.alert = () => {};
      window.confirm = () => true;
    },
  });

  // El `<script src="/static/vendor/pdf.min.js">` no se descarga: jsdom no carga
  // recursos externos y la frontera de PDF.js la pone este arnés.
  return new ViewerHarness(dom, boundary, code);
}
