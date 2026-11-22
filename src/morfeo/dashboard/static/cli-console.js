/*
 * Embedded terminal controller of the Morfeo dashboard (FAB, terminal window,
 * agent picker, WebSocket client, «Activar CLI» banner, tools notice and quick
 * commands).
 *
 * Loaded by index.html with a classic <script src> placed right before the
 * main inline script, so its globals and function declarations are shared
 * with it: inline onclick attributes and other panels (sendTerminalPrompt,
 * openMorfeoTerminal, terminalActivity, ...) call these functions, and these
 * functions call inline helpers (escapeHtml, showToast, ...) at call time.
 * The code keeps the indentation it had inside index.html.
 */

    // Cuánto se espera a que la terminal conecte y a que el agente arranque.
    let TERMINAL_READY_TIMEOUT_MS = 10000;
    let TERMINAL_BOOT_DELAY_MS = 2500;

    // Asegura una terminal con un agente que entienda los slash commands y el
    // texto libre; en Shell o AGY cambia a Claude Code y espera a que arranque.
    // Si la terminal no conecta a tiempo llama a `onFail`: quien envía tiene que
    // saber que el agente no recibió nada.
    function withCommandAgentReady(fn, onFail) {
      const isOpen = () => terminalSocket && terminalSocket.readyState === 1;
      // Sin activar, la terminal nunca conectará: se avisa en lugar de esperar.
      if (terminalAuthorized === false) {
        showActivationBanner();
        if (onFail) onFail();
        return;
      }
      const capable = TERMINAL_COMMAND_AGENTS.includes(selectedAgent);
      if (capable && isOpen()) { fn(); return; }
      // Cambiar a Claude Code cierra la sesión viva de Shell o AGY: solo con confirmación.
      if (!capable && !useTerminalAgent('claude', { connect: true })) { if (onFail) onFail(); return; }
      if (!isTerminalOpen) openMorfeoTerminal();
      else if (!isOpen()) ensureTerminalConnected(true);
      // Se cuentan ticks en lugar de leer el reloj de pared: mismo plazo en el
      // navegador y determinista bajo el reloj manual de las pruebas.
      const tick = Math.min(200, TERMINAL_READY_TIMEOUT_MS);
      let ticks = Math.ceil(TERMINAL_READY_TIMEOUT_MS / tick);
      const wait = setInterval(() => {
        ticks -= 1;
        if (!isOpen() && ticks > 0) return;
        clearInterval(wait);
        if (isOpen()) setTimeout(fn, TERMINAL_BOOT_DELAY_MS);
        else if (onFail) onFail();
      }, tick);
    }

    // Un prompt largo se escribe y se confirma por separado: enviado junto con
    // el retorno, el agente puede tomarlo como texto pegado y no enviarlo.
    // Devuelve una promesa: true cuando el prompt llegó a la terminal, false si
    // la terminal no conectó a tiempo.
    function sendTerminalPrompt(text) {
      return new Promise(resolve => {
        withCommandAgentReady(() => {
          terminalSocket.send(text);
          setTimeout(() => {
            const open = terminalSocket && terminalSocket.readyState === 1;
            if (open) terminalSocket.send('\r');
            if (terminalInstance) terminalInstance.focus();
            resolve(!!open);
          }, 200);
        }, () => resolve(false));
      });
    }

    /* ========================================================
       CONTROLADOR DEL ASISTENTE TERMINAL WEB (XTERM + PTY)
       ======================================================== */
    let terminalInstance = null;
    let fitAddonInstance = null;
    let terminalSocket = null;
    let isTerminalOpen = false;
    let isTerminalMaximized = false;
    let selectedAgent = localStorage.getItem('morfeo_terminal_agent') || 'herdr';
    let cachedTerminalTools = null;
    let monitoredProjectPath = '';
    let activeAgentPaneId = null;

    // La sesión del agente vive en el servidor (terminal.py, TerminalSession): el
    // tablero recuerda su id y se reconecta a ella al recargar o al perder la
    // conexión, y el servidor redibuja su salida reciente una vez. Cerrar la
    // ventana del CLI o cambiar de pestaña no la termina; cambiar de agente o
    // reiniciar sí, y por eso se pide confirmación.
    const TERMINAL_SESSION_KEY = `morfeo.terminalSession@${window.location.host}`;
    // La ráfaga del redibujado no cuenta como que el agente esté trabajando.
    const TERMINAL_REPLAY_QUIET_MS = 800;
    const TERMINAL_AGENT_LABELS = {
      herdr: 'Herdr (Workspace Manager)',
      claude: 'Claude Code',
      opencode: 'OpenCode',
      pi: 'Pi',
      agy: 'Antigravity (AGY)',
      shell: 'Shell (Zsh/Bash)'
    };
    // Agentes que entienden los slash commands del marco (Herdr refleja el panel del agente).
    const TERMINAL_COMMAND_AGENTS = ['claude', 'opencode', 'pi', 'herdr'];
    // Preguntas de arranque del agente: el Enter del comando las respondería a ciegas.
    const TERMINAL_STARTUP_QUESTIONS = /trust this folder|Do you trust|Enter to confirm/i;
    let terminalSessionId = null;
    let terminalSessionAgent = null;
    let terminalSessionStartedAt = 0;
    let terminalLastOutputAt = 0;
    let terminalQuietUntil = 0;
    let terminalSessionTaken = false;
    let cachedTerminalAgents = null;

    // Activación del CLI (terminal_auth.py): el servidor exige una cookie de
    // sesión para la terminal. `null` mientras no se sabe; `false` cuando el
    // servidor dijo que este navegador no está activado. Activar solo ocurre
    // con un clic en «Activar CLI», nunca al cargar la página.
    const TERMINAL_ACTIVATION_POLL_MS = 700;
    const TERMINAL_ACTIVATION_WAIT_MS = 45000;
    let terminalAuthorized = null;
    let terminalActivating = null;
    let cachedTerminalInfo = null;
    let terminalToolsNoticeDismissed = false;
    // Nombres de los emuladores que detect_terminal_tools puede preferir.
    const TERMINAL_EMULATOR_LABELS = {
      ghostty: 'Ghostty',
      wezterm: 'WezTerm',
      'gnome-terminal': 'GNOME Terminal',
      konsole: 'Konsole',
      'x-terminal-emulator': 'Terminal'
    };
    const TERMINAL_EMULATOR_HINT = 'instala un emulador de terminal (GNOME Terminal, Konsole, Ghostty o WezTerm)';

    function terminalEmulatorLabel(id) {
      return TERMINAL_EMULATOR_LABELS[id] || (id ? String(id) : 'Terminal');
    }

    function terminalAgentLabel(agent) {
      return TERMINAL_AGENT_LABELS[agent] || agent;
    }

    function storedTerminalSession() {
      try {
        const rec = JSON.parse(localStorage.getItem(TERMINAL_SESSION_KEY) || 'null');
        return rec && rec.id ? rec : null;
      } catch (err) { return null; }
    }

    function rememberTerminalSession(id, agent) {
      try { localStorage.setItem(TERMINAL_SESSION_KEY, JSON.stringify({ id, agent })); } catch (err) { /* sin almacenamiento */ }
    }

    function forgetTerminalSession(id) {
      const rec = storedTerminalSession();
      try { if (rec && (!id || rec.id === id)) localStorage.removeItem(TERMINAL_SESSION_KEY); } catch (err) { /* sin almacenamiento */ }
      if (!id || terminalSessionId === id) { terminalSessionId = null; terminalSessionAgent = null; }
    }

    function terminalSessionLive() {
      return !!terminalSessionId && !terminalProcessExited;
    }

    // Termina la sesión en el servidor (cambio de agente, reinicio o cierre de la página).
    function closeTerminalSession(keepalive = false) {
      const id = terminalSessionId;
      if (!id) return;
      forgetTerminalSession(id);
      if (typeof fetch === 'undefined') return;
      try {
        fetch(`/api/terminal/sessions/${encodeURIComponent(id)}`, { method: 'DELETE', keepalive }).catch(() => {});
      } catch (err) { /* la sesión se recoge sola al vencer */ }
    }

    // «Detener proceso»: Esc para claude, opencode y pi; Ctrl-C para shell y herdr
    // (lo decide el servidor). La sesión sigue abierta para la fase siguiente.
    async function interruptTerminalSession(id) {
      const sid = id || terminalSessionId;
      if (!sid) return { ok: false, error: 'No hay una sesión del agente abierta.' };
      try {
        const res = await fetch(`/api/terminal/sessions/${encodeURIComponent(sid)}/interrupt`, { method: 'POST' });
        const data = await res.json().catch(() => ({}));
        return res.ok ? { ok: true, key: data.key } : { ok: false, gone: res.status === 404, error: data.error || `HTTP ${res.status}` };
      } catch (err) {
        return { ok: false, error: err.message };
      }
    }

    // Lo que el seguidor de fases lee para saber si el agente está escribiendo.
    function terminalActivity() {
      return {
        sessionId: terminalSessionId,
        agent: terminalSessionAgent || selectedAgent,
        lastOutputAt: terminalLastOutputAt,
        connected: !!(terminalSocket && terminalSocket.readyState === 1)
      };
    }

    // Tras recargar: si la sesión recordada sigue viva, se reconecta en segundo
    // plano (sin abrir la ventana) para que el seguidor vea la actividad.
    async function resumeTerminalSession() {
      const rec = storedTerminalSession();
      if (!rec || typeof fetch === 'undefined') return false;
      try {
        const res = await fetch(`/api/terminal/sessions/${encodeURIComponent(rec.id)}`);
        // Sin activar no se sabe si sigue viva: se conserva para después de activar.
        if (res.status === 401) { terminalAuthorized = false; return false; }
        if (res.status === 404) { forgetTerminalSession(rec.id); return false; }
        const info = await res.json();
        if (!info || !info.alive) { forgetTerminalSession(rec.id); return false; }
        selectedAgent = info.agent;
        const select = document.getElementById('terminalAgentSelect');
        if (select) select.value = info.agent;
        terminalSessionId = info.id;
        terminalSessionAgent = info.agent;
        if (!terminalInstance) setupTerminal();
        else ensureTerminalConnected(true);
        return true;
      } catch (err) {
        // Un fallo pasajero conserva el registro: la próxima carga puede reconectarse.
        return false;
      }
    }

    // Cambia el agente del CLI. Con una sesión viva de otro agente, o con `fresh`,
    // la sesión se cierra, y eso nunca pasa sin confirmación. Devuelve false si
    // el operador decide conservarla.
    function useTerminalAgent(agent, opts = {}) {
      const live = terminalSessionLive();
      const current = terminalSessionAgent || selectedAgent;
      const restart = agent !== current || (opts.fresh && live);
      if (!restart) {
        if (agent !== selectedAgent) selectedAgent = agent;
        return true;
      }
      if (live) {
        const question = agent === current
          ? `Esto cierra la sesión actual de ${terminalAgentLabel(current)} y abre una nueva; se pierde su conversación. ¿Continuar?`
          : `Esto cierra la sesión de ${terminalAgentLabel(current)} y abre ${terminalAgentLabel(agent)}; se pierde su conversación. ¿Continuar?`;
        if (!window.confirm(question)) {
          const select = document.getElementById('terminalAgentSelect');
          if (select) select.value = current;
          return false;
        }
      }
      selectedAgent = agent;
      try { localStorage.setItem('morfeo_terminal_agent', agent); } catch (err) { /* sin almacenamiento */ }
      const select = document.getElementById('terminalAgentSelect');
      if (select) select.value = agent;
      closeTerminalSession();
      if (terminalInstance) {
        terminalInstance.reset();
        terminalInstance.write(`\r\n\x1b[36m⚡ Conectando terminal con ${terminalAgentLabel(agent)}...\x1b[0m\r\n`);
      }
      if (terminalInstance && (isTerminalOpen || opts.connect)) connectTerminalWs(agent, { fresh: true });
      return true;
    }

    // La pantalla visible como texto, para no responder una pregunta de arranque
    // con el Enter del comando.
    function terminalScreenText() {
      const buffer = terminalInstance && terminalInstance.buffer && terminalInstance.buffer.active;
      if (!buffer) return '';
      const lines = [];
      for (let y = 0; y < terminalInstance.rows; y++) {
        const line = buffer.getLine(buffer.viewportY + y);
        if (line) lines.push(line.translateToString(true));
      }
      return lines.join('\n');
    }

    // Un agente recién abierto pinta su prompt antes de leer: se espera su primera
    // salida y luego una pausa breve, con un tope.
    let TERMINAL_SETTLE_MAX_MS = 12000;
    function settleTerminal(maxMs = TERMINAL_SETTLE_MAX_MS) {
      return new Promise(resolve => {
        const tick = Math.min(250, Math.max(1, maxMs));
        let ticks = Math.ceil(maxMs / tick);
        const wait = setInterval(() => {
          ticks -= 1;
          const quiet = terminalLastOutputAt > 0 && terminalLastOutputAt >= terminalSessionStartedAt && Date.now() - terminalLastOutputAt > 900;
          if (quiet || ticks <= 0) { clearInterval(wait); resolve(); }
        }, tick);
      });
    }

    async function checkTerminalTools() {
      if (typeof fetch === 'undefined') {
        return { ready: true, preferred_terminal: 'ghostty', herdr: { installed: true, client_running: true } };
      }
      try {
        const res = await fetch('/api/terminal/tools');
        if (res.status === 401) { terminalAuthorized = false; return null; }
        const data = await res.json();
        if (data && data.ok && data.tools) {
          cachedTerminalTools = data.tools;
          monitoredProjectPath = data.tools.monitored_path || '';
          activeAgentPaneId = data.tools.active_pane || null;
          updateTerminalFooterPath();
          updateExternalLaunchButton();
          return data.tools;
        }
      } catch (err) {
        console.warn('Error verificando herramientas de terminal:', err);
      }
      return null;
    }

    function updateTerminalFooterPath() {
      const el = document.getElementById('terminalFooterRun');
      if (el && monitoredProjectPath) {
        el.textContent = monitoredProjectPath;
        el.title = monitoredProjectPath;
      }
    }

    // Lo que falta para el terminal externo, en palabras.
    function missingToolsText(tools) {
      const names = ((tools && tools.missing) || []).map(item => {
        if (item === 'herdr') return 'Herdr';
        if (item === 'terminal') return 'Ghostty o WezTerm';
        if (item === 'terminal emulator') return 'un emulador de terminal (GNOME Terminal, Konsole, Ghostty o WezTerm)';
        return String(item);
      });
      return names.length ? names.join(' y ') : 'herramientas del terminal externo';
    }

    // Cómo instalar lo que falta: Homebrew en macOS, una pista genérica en Linux.
    function missingToolsHints(tools) {
      const missing = (tools && tools.missing) || [];
      const hints = [];
      if (missing.includes('herdr')) hints.push('brew install herdr');
      if (missing.includes('terminal')) hints.push('brew install --cask ghostty');
      if (missing.includes('terminal emulator')) hints.push(TERMINAL_EMULATOR_HINT);
      return hints;
    }

    // Una herramienta que falta solo desactiva el botón del terminal externo:
    // el CLI embebido sigue funcionando.
    function updateExternalLaunchButton() {
      const btn = document.getElementById('btnLaunchExternalTerm');
      if (!btn || !cachedTerminalTools) return;
      const pref = cachedTerminalTools.preferred_terminal;
      const name = terminalEmulatorLabel(pref);
      btn.textContent = `🖥️ ${name}`;
      btn.disabled = !cachedTerminalTools.ready;
      btn.title = cachedTerminalTools.ready
        ? (pref ? `Traer al frente o abrir en ${name} con Herdr` : 'Abrir en terminal nativo')
        : `No disponible: falta ${missingToolsText(cachedTerminalTools)}`;
    }

    // Aviso descartable, dentro de la ventana del CLI, de lo que falta para el
    // terminal externo. No cierra ni bloquea la terminal embebida.
    function showToolsNotice(tools) {
      if (terminalToolsNoticeDismissed || !tools || tools.ready) return;
      const win = document.getElementById('morfeoTerminalWindow');
      const body = document.getElementById('morfeoTerminalBody');
      if (!win || document.getElementById('cliToolsNotice')) return;
      const notice = document.createElement('div');
      notice.id = 'cliToolsNotice';
      notice.setAttribute('role', 'status');
      notice.style.cssText = 'display:flex;flex-wrap:wrap;align-items:center;gap:0.4rem 0.75rem;'
        + 'padding:0.45rem 0.85rem;background:var(--warn-dim, rgba(245,158,11,.15));'
        + 'border-bottom:1px solid var(--warn, #f59e0b);color:var(--text, #f9fafb);font-size:0.75rem;line-height:1.35;';
      const text = document.createElement('span');
      text.style.cssText = 'flex:1 1 14rem;min-width:0;overflow-wrap:anywhere;';
      text.textContent = `El CLI embebido funciona; el terminal externo no está disponible porque falta ${missingToolsText(tools)}.`;
      const hints = missingToolsHints(tools);
      if (hints.length) {
        const hint = document.createElement('code');
        hint.style.cssText = 'display:block;margin-top:0.2rem;font-family:var(--font-mono, monospace);color:var(--text-muted, #9ca3af);';
        hint.textContent = hints.join(' · ');
        text.appendChild(hint);
      }
      const close = document.createElement('button');
      close.type = 'button';
      close.textContent = '×';
      close.title = 'Cerrar aviso';
      close.setAttribute('aria-label', 'Cerrar aviso');
      close.style.cssText = 'background:none;border:0;color:inherit;font-size:1.1rem;line-height:1;cursor:pointer;padding:0 0.2rem;';
      close.addEventListener('click', () => {
        terminalToolsNoticeDismissed = true;
        notice.remove();
        if (fitAddonInstance) fitAddonInstance.fit();
      });
      notice.append(text, close);
      if (body && body.parentNode === win) win.insertBefore(notice, body);
      else win.appendChild(notice);
    }

    function setTerminalAgentOptions(agents) {
      const selectEl = document.getElementById('terminalAgentSelect');
      if (!selectEl) return;
      const isAvailable = a => (a.available !== undefined ? !!a.available : a.installed !== false);
      selectEl.innerHTML = '';
      agents.forEach(a => {
        const opt = document.createElement('option');
        opt.value = a.id;
        const usable = isAvailable(a);
        opt.textContent = `${a.name || terminalAgentLabel(a.id)}${usable ? '' : ' (no instalado)'}`;
        opt.disabled = !usable;
        if (a.desc) opt.title = a.desc;
        selectEl.appendChild(opt);
      });
      const usable = agents.filter(isAvailable).map(a => a.id);
      // Con una sesión viva se respeta su agente; si no, un agente no instalado
      // cede el lugar al que el servidor propone.
      if (!terminalSessionId && usable.length && !usable.includes(selectedAgent)) {
        const fallback = cachedTerminalInfo && usable.includes(cachedTerminalInfo.default) ? cachedTerminalInfo.default : usable[0];
        selectedAgent = fallback;
      }
      if ([...selectEl.options].some(o => o.value === selectedAgent)) selectEl.value = selectedAgent;
    }

    // Los comandos rápidos son los slash commands del workspace (.claude/commands)
    // que lista el servidor; reemplazan a los atajos fijos del pie.
    function setTerminalQuickCommands(quick) {
      const actions = document.querySelector('#morfeoTerminalWindow .terminal-footer-actions');
      if (!actions) return;
      actions.querySelectorAll('button').forEach(b => {
        if (/sendTerminalQuickCommand/.test(b.getAttribute('onclick') || '')) b.remove();
      });
      let select = document.getElementById('terminalQuickSelect');
      if (!select) {
        select = document.createElement('select');
        select.id = 'terminalQuickSelect';
        select.className = 'btn-term-shortcut';
        select.setAttribute('aria-label', 'Comandos rápidos');
        select.title = 'Comandos rápidos del workspace';
        // Width limits live in index.html (#terminalQuickSelect) so phones can shrink it.
        select.style.cssText = 'min-width:0;cursor:pointer;';
        select.addEventListener('change', () => {
          const cmd = select.value;
          select.value = '';
          if (cmd) sendTerminalQuickCommand(cmd);
        });
        actions.insertBefore(select, actions.firstChild);
      }
      select.innerHTML = '';
      const placeholder = document.createElement('option');
      placeholder.value = '';
      placeholder.textContent = 'Comandos…';
      select.appendChild(placeholder);
      quick.forEach(item => {
        const name = item && typeof item === 'object' ? item.name : item;
        if (!name) return;
        const opt = document.createElement('option');
        opt.value = String(name);
        opt.textContent = String(name);
        if (item && item.description) opt.title = String(item.description);
        select.appendChild(opt);
      });
      select.value = '';
      select.disabled = select.options.length <= 1;
    }

    // Lo que dice /api/terminal/agents: si el CLI está habilitado, si este
    // navegador está activado, sus agentes y los comandos rápidos.
    async function fetchTerminalInfo() {
      if (typeof fetch === 'undefined') return null;
      try {
        const res = await fetch('/api/terminal/agents');
        const data = await res.json();
        return data && data.ok ? data : null;
      } catch (err) {
        return null;
      }
    }

    function applyTerminalInfo(data) {
      if (!data) return;
      cachedTerminalInfo = data;
      if (typeof data.authorized === 'boolean') terminalAuthorized = data.authorized;
      if (Array.isArray(data.agents) && data.agents.length) {
        cachedTerminalAgents = data.agents;
        setTerminalAgentOptions(data.agents);
      }
      if (Array.isArray(data.quick)) setTerminalQuickCommands(data.quick);
      if (data.enabled !== false && data.authorized === false) showActivationBanner();
      else if (data.authorized === true) hideActivationBanner();
    }

    // Banner rojo de un navegador sin la cookie del CLI (una pestaña vieja, un
    // marcador, un servidor reiniciado). Se crea aquí y no en index.html.
    function showActivationBanner() {
      let banner = document.getElementById('cliActivationBanner');
      if (banner) return banner;
      banner = document.createElement('div');
      banner.id = 'cliActivationBanner';
      banner.setAttribute('role', 'alert');
      banner.style.cssText = 'position:fixed;top:12px;left:50%;transform:translateX(-50%);z-index:100000;'
        + 'box-sizing:border-box;width:max-content;max-width:calc(100vw - 24px);'
        + 'display:flex;flex-wrap:wrap;align-items:center;gap:0.4rem 0.75rem;padding:0.6rem 0.85rem;'
        + 'background:#7f1d1d;color:#fff;border:1px solid var(--bad, #ef4444);border-radius:var(--radius, 8px);'
        + 'box-shadow:0 4px 16px rgba(0,0,0,.35);font:0.85rem/1.4 var(--font-sans, system-ui, sans-serif);';
      const text = document.createElement('span');
      text.id = 'cliActivationText';
      text.style.cssText = 'font-weight:600;flex:1 1 12rem;min-width:0;';
      text.textContent = 'El CLI del tablero no está activado';
      const activate = document.createElement('button');
      activate.type = 'button';
      activate.id = 'cliActivateBtn';
      activate.textContent = 'Activar CLI';
      activate.style.cssText = 'background:#fff;color:#7f1d1d;border:0;border-radius:6px;padding:0.3rem 0.7rem;'
        + 'font-weight:700;cursor:pointer;white-space:nowrap;';
      activate.addEventListener('click', () => { ensureAuthorized().catch(() => {}); });
      const close = document.createElement('button');
      close.type = 'button';
      close.textContent = '×';
      close.title = 'Ocultar aviso';
      close.setAttribute('aria-label', 'Ocultar aviso');
      close.style.cssText = 'background:none;border:0;color:#fff;font-size:1.15rem;line-height:1;cursor:pointer;padding:0 0.2rem;';
      close.addEventListener('click', () => banner.remove());
      const note = document.createElement('span');
      note.id = 'cliActivationNote';
      note.style.cssText = 'flex:1 1 100%;font-size:0.78rem;opacity:0.9;overflow-wrap:anywhere;';
      note.hidden = true;
      banner.append(text, activate, close, note);
      document.body.appendChild(banner);
      return banner;
    }

    function hideActivationBanner() {
      const banner = document.getElementById('cliActivationBanner');
      if (banner) banner.remove();
    }

    function setActivationNote(message, link) {
      const banner = showActivationBanner();
      const note = banner.querySelector('#cliActivationNote');
      if (!note) return;
      note.textContent = message;
      if (link) {
        const a = document.createElement('a');
        a.href = link;
        a.textContent = link;
        a.style.cssText = 'color:#fff;text-decoration:underline;margin-left:0.3rem;';
        note.appendChild(a);
      }
      note.hidden = !message;
    }

    // Pregunta cada 0,7 s si este navegador ya tiene la cookie, hasta 45 s. Se
    // cuentan ticks (no el reloj): mismo plazo bajo el reloj manual de las pruebas.
    function pollTerminalAuthorization() {
      return new Promise(resolve => {
        let ticks = Math.ceil(TERMINAL_ACTIVATION_WAIT_MS / TERMINAL_ACTIVATION_POLL_MS);
        let busy = false;
        let done = false;
        const finish = (value) => { done = true; clearInterval(timer); resolve(value); };
        const timer = setInterval(async () => {
          if (busy || done) return;
          ticks -= 1;
          busy = true;
          const info = await fetchTerminalInfo();
          busy = false;
          if (done) return;
          if (info && info.authorized) finish(info);
          else if (ticks <= 0) finish(null);
        }, TERMINAL_ACTIVATION_POLL_MS);
      });
    }

    // «Activar CLI»: el servidor abre su enlace de activación en el navegador
    // del sistema (el secreto nunca llega a esta página), ese navegador recibe
    // la cookie y esta pestaña espera hasta quedar autorizada; entonces abre la
    // sesión. Solo con un clic, nunca al cargar.
    async function ensureAuthorized() {
      if (terminalActivating) return terminalActivating;
      terminalActivating = (async () => {
        if (terminalAuthorized !== false) {
          const info = await fetchTerminalInfo();
          if (info) applyTerminalInfo(info);
          if (!info || info.authorized !== false || info.enabled === false) return info;
        }
        setActivationNote('Abriendo el enlace de activación en el navegador…');
        let result = {};
        try {
          const res = await fetch('/api/terminal/activate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: '{}'
          });
          result = await res.json().catch(() => ({}));
          // 429: el enlace ya se abrió hace un momento; basta con esperar.
          if (!res.ok && res.status !== 429) {
            setActivationNote(`No se pudo activar: ${result.error || `HTTP ${res.status}`}. Abre el enlace que imprimió morfeo ui.`);
            return cachedTerminalInfo;
          }
        } catch (err) {
          setActivationNote('No se pudo contactar al servidor. Abre el enlace que imprimió morfeo ui.');
          return cachedTerminalInfo;
        }
        // La cookie pertenece a la dirección del servidor: una pestaña abierta
        // con otro nombre (localhost por 127.0.0.1) nunca la recibe.
        const here = window.location.origin;
        if (result.origin && /^https?:\/\/[^\s"'<>]+$/.test(result.origin) && result.origin !== here) {
          setActivationNote('El CLI se activa en otra dirección; abre el tablero en', `${result.origin}/`);
          return cachedTerminalInfo;
        }
        const info = await pollTerminalAuthorization();
        if (!info) {
          setActivationNote('No llegó la activación. Abre el enlace que imprimió morfeo ui o vuelve a intentarlo.');
          return cachedTerminalInfo;
        }
        applyTerminalInfo(info);
        hideActivationBanner();
        checkTerminalTools();
        if (!isTerminalOpen) openMorfeoTerminal();
        else if (terminalInstance) connectTerminalWs(selectedAgent);
        else setupTerminal();
        return info;
      })();
      try {
        return await terminalActivating;
      } finally {
        terminalActivating = null;
      }
    }

    function initTerminalUI() {
      const select = document.getElementById('terminalAgentSelect');
      if (select) {
        select.value = selectedAgent;
      }
      // Solo lee: activar el CLI espera el clic en «Activar CLI».
      fetchTerminalInfo().then(data => {
        applyTerminalInfo(data);
        if (!data || data.authorized !== false) checkTerminalTools();
      }).catch(() => {});
    }

    function toggleMorfeoTerminal() {
      if (isTerminalOpen) {
        closeMorfeoTerminal();
        return;
      }

      // La terminal embebida se abre siempre; lo que falte para el terminal
      // externo solo desactiva su botón y deja un aviso descartable.
      openMorfeoTerminal();
      if (terminalAuthorized === false) {
        showActivationBanner();
        return;
      }

      if (typeof fetch !== 'undefined') {
        checkTerminalTools().then(tools => {
          if (tools && !tools.ready) showToolsNotice(tools);
        }).catch(() => {});
      }
    }

    function showToolsRequiredModal(tools) {
      const modal = document.getElementById('morfeoToolsRequiredModal');
      const body = document.getElementById('morfeoToolsModalBody');
      if (!modal || !body) return;

      const missing = (tools && tools.missing) || [];
      const hasHerdr = tools && tools.herdr && tools.herdr.installed;
      const hasGhostty = tools && tools.ghostty && tools.ghostty.installed;
      const hasWezterm = tools && tools.wezterm && tools.wezterm.installed;
      const linuxEmulator = missing.includes('terminal emulator');
      const hasTerminal = !!(tools && tools.preferred_terminal) || ((hasGhostty || hasWezterm) && !linuxEmulator);

      let html = `
        <p style="margin-bottom:0.75rem;">Para visualizar la pantalla de terminal como un espejo interactivo de <strong>Herdr</strong> y operar en el entorno nativo del proyecto, se requiere contar con las herramientas correspondientes:</p>
      `;

      if (!hasHerdr) {
        html += `
          <div class="tools-pkg-card is-missing">
            <div class="tools-pkg-title">
              <span>✕ Herdr (Workspace Manager de IA)</span>
              <span style="color:#ef4444;font-size:0.75rem;font-weight:700;">No instalado</span>
            </div>
            <div style="font-size:0.8rem;color:#94a3b8;">Gestor de sesiones persistentes y workspaces de agentes. Para instalarlo:</div>
            <div class="tools-cmd-box">brew install herdr</div>
          </div>
        `;
      } else {
        html += `
          <div class="tools-pkg-card is-ok">
            <div class="tools-pkg-title">
              <span>✓ Herdr</span>
              <span style="color:#10b981;font-size:0.75rem;font-weight:700;">Instalado</span>
            </div>
          </div>
        `;
      }

      if (!hasTerminal && linuxEmulator) {
        html += `
          <div class="tools-pkg-card is-missing">
            <div class="tools-pkg-title">
              <span>✕ Emulador de Terminal</span>
              <span style="color:#ef4444;font-size:0.75rem;font-weight:700;">No instalado</span>
            </div>
            <div style="font-size:0.8rem;color:#94a3b8;">Para abrir la consola nativa, ${TERMINAL_EMULATOR_HINT}.</div>
          </div>
        `;
      } else if (!hasTerminal) {
        html += `
          <div class="tools-pkg-card is-missing">
            <div class="tools-pkg-title">
              <span>✕ Emulador de Terminal (Ghostty o WezTerm)</span>
              <span style="color:#ef4444;font-size:0.75rem;font-weight:700;">No instalado</span>
            </div>
            <div style="font-size:0.8rem;color:#94a3b8;">Se requiere Ghostty (prioritario) o WezTerm para ejecutar la consola nativa:</div>
            <div class="tools-cmd-box">brew install --cask ghostty</div>
            <div style="margin-top:0.35rem;font-size:0.75rem;color:#64748b;">Alternativa: <code>brew install --cask wezterm</code></div>
          </div>
        `;
      } else {
        const termName = tools && tools.preferred_terminal
          ? terminalEmulatorLabel(tools.preferred_terminal)
          : (hasGhostty ? 'Ghostty (prioritario)' : 'WezTerm');
        html += `
          <div class="tools-pkg-card is-ok">
            <div class="tools-pkg-title">
              <span>✓ Emulador de Terminal: ${escapeTerminalText(termName)}</span>
              <span style="color:#10b981;font-size:0.75rem;font-weight:700;">Instalado</span>
            </div>
          </div>
        `;
      }

      html += `
        <p style="margin-top:0.85rem;font-size:0.8rem;color:#94a3b8;">
          Ruta del proyecto monitoreado: <code style="color:#38bdf8;">${escapeTerminalText(monitoredProjectPath || 'Directorio del workspace')}</code>
        </p>
      `;

      body.innerHTML = html;
      modal.classList.add('is-open');
    }

    function escapeTerminalText(value) {
      return String(value).replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
    }

    function closeToolsRequiredModal() {
      const modal = document.getElementById('morfeoToolsRequiredModal');
      if (modal) modal.classList.remove('is-open');
    }

    function proceedWithBasicShell() {
      closeToolsRequiredModal();
      selectedAgent = 'shell';
      const select = document.getElementById('terminalAgentSelect');
      if (select) select.value = 'shell';
      openMorfeoTerminal();
    }

    async function launchExternalTerminal() {
      try {
        const res = await fetch('/api/terminal/launch-external', { method: 'POST' });
        if (res.status === 401) { terminalAuthorized = false; showActivationBanner(); return; }
        const data = await res.json();
        if (data && data.ok) {
          const name = terminalEmulatorLabel(data.terminal);
          const act = data.action === 'activated' ? 'enfocado' : 'iniciado';
          console.log(`[Morfeo] Terminal ${name} ${act} en: ${data.cwd}`);
        } else {
          alert('No fue posible abrir el terminal nativo: ' + (data.error || 'Desconocido'));
        }
      } catch (err) {
        alert('Error de conexión al abrir terminal nativo: ' + err.message);
      }
    }

    let terminalPingTimer = null;
    let terminalReconnectTimer = null;
    let terminalProcessExited = false;

    function ensureTerminalConnected(forceRedraw = false) {
      if (!isTerminalOpen && !terminalSessionId) return;
      if (!terminalInstance) {
        setupTerminal();
        return;
      }
      const sockDead = !terminalSocket || (
        terminalSocket.readyState !== WebSocket.OPEN &&
        terminalSocket.readyState !== WebSocket.CONNECTING
      );
      if (sockDead) {
        terminalProcessExited = false;
        connectTerminalWs(selectedAgent);
      } else if (terminalSocket.readyState === WebSocket.OPEN && isTerminalOpen) {
        if (fitAddonInstance) fitAddonInstance.fit();
        sendTerminalResize(forceRedraw);
      }
      if (isTerminalOpen) terminalInstance.focus();
    }

    function openMorfeoTerminal() {
      const win = document.getElementById('morfeoTerminalWindow');
      const fab = document.getElementById('morfeoAssistantFab');
      if (!win) return;
      isTerminalOpen = true;
      win.classList.add('is-open');
      if (fab) fab.classList.add('is-active');

      if (!terminalInstance) {
        setupTerminal();
      } else {
        setTimeout(() => {
          ensureTerminalConnected(true);
        }, 80);
      }
    }

    function closeMorfeoTerminal() {
      const win = document.getElementById('morfeoTerminalWindow');
      const fab = document.getElementById('morfeoAssistantFab');
      if (!win) return;
      isTerminalOpen = false;
      win.classList.remove('is-open');
      if (fab) fab.classList.remove('is-active');
    }

    function toggleMaximizeTerminal() {
      const win = document.getElementById('morfeoTerminalWindow');
      const btn = document.getElementById('terminalMaximizeBtn');
      if (!win) return;
      isTerminalMaximized = !isTerminalMaximized;
      win.classList.toggle('is-maximized', isTerminalMaximized);
      if (btn) {
        btn.textContent = isTerminalMaximized ? '🗗' : '⛶';
        btn.title = isTerminalMaximized ? 'Restaurar tamaño' : 'Maximizar';
      }
      setTimeout(() => {
        if (fitAddonInstance) fitAddonInstance.fit();
        sendTerminalResize(true);
        if (terminalInstance) terminalInstance.focus();
      }, 150);
    }

    function setupTerminal() {
      const container = document.getElementById('xtermContainer');
      if (!container || typeof Terminal === 'undefined') return;

      terminalInstance = new Terminal({
        cursorBlink: true,
        fontSize: terminalFontSize(),
        lineHeight: 1.25,
        fontFamily: 'ui-monospace, "SF Mono", Menlo, Consolas, monospace',
        theme: {
          background: '#080c14',
          foreground: '#f1f5f9',
          cursor: '#38bdf8',
          cursorAccent: '#080c14',
          selectionBackground: 'rgba(56, 189, 248, 0.35)',
          black: '#0f172a',
          red: '#ef4444',
          green: '#10b981',
          yellow: '#f59e0b',
          blue: '#38bdf8',
          magenta: '#d946ef',
          cyan: '#06b6d4',
          white: '#f8fafc',
          brightBlack: '#475569',
          brightRed: '#f87171',
          brightGreen: '#34d399',
          brightYellow: '#fbbf24',
          brightBlue: '#60a5fa',
          brightMagenta: '#e879f9',
          brightCyan: '#22d3ee',
          brightWhite: '#ffffff'
        }
      });

      if (typeof FitAddon !== 'undefined' && FitAddon.FitAddon) {
        fitAddonInstance = new FitAddon.FitAddon();
        terminalInstance.loadAddon(fitAddonInstance);
      }

      terminalInstance.open(container);

      container.addEventListener('mousedown', () => {
        if (terminalInstance) terminalInstance.focus();
      });

      setTimeout(() => {
        if (fitAddonInstance) fitAddonInstance.fit();
        connectTerminalWs(selectedAgent);
        // Reconectado en segundo plano no toma el foco: el teclado seguiría en la terminal oculta.
        if (isTerminalOpen) terminalInstance.focus();
      }, 100);

      terminalInstance.onData(data => {
        if (terminalSocket && terminalSocket.readyState === WebSocket.OPEN) {
          terminalSocket.send(data);
        } else if (isTerminalOpen) {
          terminalSessionTaken = false;
          ensureTerminalConnected(true);
        }
      });

      terminalInstance.onBinary(data => {
        if (terminalSocket && terminalSocket.readyState === WebSocket.OPEN) {
          terminalSocket.send(data);
        }
      });
    }

    function connectTerminalWs(agent, opts = {}) {
      if (terminalReconnectTimer) {
        clearTimeout(terminalReconnectTimer);
        terminalReconnectTimer = null;
      }
      if (terminalPingTimer) {
        clearInterval(terminalPingTimer);
        terminalPingTimer = null;
      }
      if (terminalSocket) {
        const oldSock = terminalSocket;
        terminalSocket = null;
        oldSock.onopen = null;
        oldSock.onclose = null;
        oldSock.onerror = null;
        oldSock.onmessage = null;
        try { oldSock.close(); } catch(e) {}
      }

      terminalProcessExited = false;
      terminalSessionTaken = false;
      // Sin la cookie del CLI el servidor rechaza la conexión: no se intenta
      // (ni se reintenta en bucle) hasta activar.
      if (terminalAuthorized === false) {
        updateTerminalStatus('disconnected', agent);
        showActivationBanner();
        if (terminalInstance && isTerminalOpen) {
          terminalInstance.write('\r\n\x1b[33m[Morfeo] El CLI del tablero no está activado: usa «Activar CLI».\x1b[0m\r\n');
        }
        return;
      }
      updateTerminalStatus('connecting', agent);

      // Se reconecta a la sesión viva del mismo agente; el servidor abre una nueva
      // si ya no existe o si `fresh` la descarta.
      const stored = storedTerminalSession();
      const resumeId = opts.fresh ? null
        : (terminalSessionId && terminalSessionAgent === agent ? terminalSessionId
          : (stored && stored.agent === agent ? stored.id : null));
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const cols = terminalInstance ? terminalInstance.cols : 80;
      const rows = terminalInstance ? terminalInstance.rows : 24;
      const wsUrl = `${proto}//${window.location.host}/ws/terminal?agent=${encodeURIComponent(agent)}&cols=${cols}&rows=${rows}${resumeId ? `&session=${encodeURIComponent(resumeId)}` : ''}`;

      let ws = null;
      try {
        ws = new WebSocket(wsUrl);
        terminalSocket = ws;
      } catch (err) {
        console.error('Error instanciando WebSocket del terminal:', err);
        updateTerminalStatus('error', agent);
        return;
      }

      ws.binaryType = 'arraybuffer';
      let wsOpened = false;

      ws.onopen = () => {
        if (terminalSocket !== ws) return;
        wsOpened = true;
        updateTerminalStatus('connected', agent);
        // Oculta, la terminal no tiene medidas reales: no se le cambia el tamaño al agente.
        if (isTerminalOpen) {
          if (fitAddonInstance) fitAddonInstance.fit();
          sendTerminalResize(true);
        }
        if (isTerminalOpen && terminalInstance) {
          terminalInstance.focus();
        }
        terminalPingTimer = setInterval(() => {
          if (terminalSocket === ws && ws.readyState === WebSocket.OPEN) {
            try {
              ws.send(JSON.stringify({ type: 'ping' }));
            } catch (_) {}
          }
        }, 15000);
      };

      ws.onmessage = (event) => {
        if (terminalSocket !== ws || !terminalInstance) return;
        if (typeof event.data === 'string' && event.data.startsWith('{"type"')) {
          let msg = null;
          try { msg = JSON.parse(event.data); } catch (_) {}
          if (msg && msg.type === 'session') {
            // El servidor anuncia la sesión y enseguida redibuja su salida reciente:
            // se limpia antes, para que se dibuje una sola vez.
            if (msg.id !== terminalSessionId || !msg.reattached) terminalSessionStartedAt = Date.now();
            terminalSessionId = msg.id;
            terminalSessionAgent = msg.agent;
            rememberTerminalSession(msg.id, msg.agent);
            terminalInstance.reset();
            terminalQuietUntil = Date.now() + TERMINAL_REPLAY_QUIET_MS;
            return;
          }
          if (msg && msg.type === 'ended') {
            // Se cerró en el servidor (otra pestaña, el tope de sesiones): no se reconecta a ella.
            terminalProcessExited = true;
            forgetTerminalSession(terminalSessionId);
            terminalInstance.write('\r\n\x1b[33m[Morfeo] La sesión se cerró. Vuelve a abrir el asistente o reinícialo para empezar otra.\x1b[0m\r\n');
            return;
          }
          if (msg && msg.type === 'detached') {
            // Otra pestaña tomó la sesión; reconectarse aquí se la quitaría.
            terminalSessionTaken = true;
            terminalInstance.write('\r\n\x1b[33m[Morfeo] La sesión se abrió en otra pestaña. Escribe aquí o vuelve a abrir el asistente para retomarla.\x1b[0m\r\n');
            return;
          }
        }
        if (Date.now() >= terminalQuietUntil) terminalLastOutputAt = Date.now();
        if (event.data instanceof ArrayBuffer) {
          const bytes = new Uint8Array(event.data);
          try {
            const textSample = new TextDecoder('utf-8', { fatal: false }).decode(bytes);
            if (textSample.includes('[Morfeo] Sesión finalizada')) {
              terminalProcessExited = true;
              forgetTerminalSession(terminalSessionId);
            }
          } catch (_) {}
          terminalInstance.write(bytes);
        } else {
          if (typeof event.data === 'string' && event.data.includes('[Morfeo] Sesión finalizada')) {
            terminalProcessExited = true;
          }
          terminalInstance.write(event.data);
        }
      };

      ws.onclose = () => {
        if (terminalSocket === ws) {
          if (terminalPingTimer) {
            clearInterval(terminalPingTimer);
            terminalPingTimer = null;
          }
          updateTerminalStatus('disconnected', agent);
          // Rechazada antes de abrir: quizá la cookie ya no vale (servidor
          // reiniciado). Se pregunta, y sin autorización no se reintenta.
          if (!wsOpened) {
            fetchTerminalInfo().then(info => {
              if (info && info.authorized === false) applyTerminalInfo(info);
            }).catch(() => {});
          }
          // Se reconecta a la misma sesión (la conexión cayó, el agente sigue).
          const wanted = () => (isTerminalOpen || terminalSessionId) && !terminalProcessExited && !terminalSessionTaken && terminalAuthorized !== false;
          if (wanted() && !document.hidden) {
            terminalReconnectTimer = setTimeout(() => {
              if (wanted() && terminalSocket === ws) {
                connectTerminalWs(selectedAgent);
              }
            }, 600);
          }
        }
      };

      ws.onerror = (err) => {
        if (terminalSocket === ws) {
          console.warn('WebSocket terminal error:', err);
          updateTerminalStatus('disconnected', agent);
        }
      };
    }

    // The terminal draws in px, so it follows the text-size control itself
    // (text-size.js): 13 px at ×1, scaled and rounded, refitted on a change.
    const TERMINAL_BASE_FONT_PX = 13;
    function terminalFontSize() {
      const scale = Number(document.documentElement.dataset.textScale) || 1;
      return Math.round(TERMINAL_BASE_FONT_PX * scale);
    }
    document.addEventListener('textscalechange', () => {
      if (!terminalInstance || !terminalInstance.options) return;
      terminalInstance.options.fontSize = terminalFontSize();
      if (fitAddonInstance) fitAddonInstance.fit();
      sendTerminalResize(true);
    });

    function sendTerminalResize(forceRedraw = false) {
      if (terminalInstance && terminalSocket && terminalSocket.readyState === WebSocket.OPEN) {
        const resizePayload = JSON.stringify({
          type: 'resize',
          cols: terminalInstance.cols,
          rows: terminalInstance.rows,
          redraw: Boolean(forceRedraw)
        });
        terminalSocket.send(resizePayload);
      }
    }

    function updateTerminalStatus(state, agent) {
      const dot = document.getElementById('terminalStatusDot');
      const badge = document.getElementById('morfeoFabBadge');
      const footerAgent = document.getElementById('terminalFooterAgent');
      const footerRun = document.getElementById('terminalFooterRun');

      const agentMap = {
        'herdr': 'Herdr (Workspace Manager)',
        'claude': 'Claude Code',
        'opencode': 'OpenCode',
        'pi': 'Pi',
        'agy': 'Antigravity (AGY)',
        'shell': 'Shell (Zsh/Bash)'
      };
      const agentLabel = agentMap[agent] || agent;

      if (footerAgent) footerAgent.textContent = agentLabel;
      if (footerRun) {
        if (monitoredProjectPath) {
          footerRun.textContent = monitoredProjectPath;
          footerRun.title = monitoredProjectPath;
        } else if (window.LAST_STATUS_PAYLOAD && window.LAST_STATUS_PAYLOAD.active_run) {
          footerRun.textContent = `proposals/${window.LAST_STATUS_PAYLOAD.active_run}`;
        }
      }

      if (dot) {
        dot.className = 'terminal-status-dot';
        if (state === 'connected') {
          dot.classList.add('is-connected');
          dot.title = `Conectado a ${agentLabel}`;
        } else if (state === 'connecting') {
          dot.classList.add('is-connecting');
          dot.title = `Conectando con ${agentLabel}...`;
        } else {
          dot.title = `Desconectado (${agentLabel})`;
        }
      }

      if (badge) {
        badge.style.background = state === 'connected' ? '#10b981' : (state === 'connecting' ? '#f59e0b' : '#6b7280');
      }
    }

    function onTerminalAgentChange() {
      const select = document.getElementById('terminalAgentSelect');
      if (!select) return;
      if (!useTerminalAgent(select.value, { connect: true })) return;
      if (!terminalInstance && isTerminalOpen) setupTerminal();
      if (terminalInstance && isTerminalOpen) terminalInstance.focus();
    }

    function restartTerminalSession() {
      if (terminalSessionLive() && !window.confirm(`Esto cierra la sesión de ${terminalAgentLabel(terminalSessionAgent || selectedAgent)} y abre una nueva; se pierde su conversación. ¿Continuar?`)) return;
      closeTerminalSession();
      if (terminalInstance) {
        terminalInstance.reset();
        terminalInstance.clear();
        terminalInstance.write('\r\n\x1b[36m⚡ Reiniciando sesión de terminal...\x1b[0m\r\n');
      }
      connectTerminalWs(selectedAgent, { fresh: true });
      if (terminalInstance) terminalInstance.focus();
    }

    function sendTerminalQuickCommand(cmd) {
      if (!terminalSocket || terminalSocket.readyState !== WebSocket.OPEN) {
        if (!isTerminalOpen) {
          openMorfeoTerminal();
        } else {
          ensureTerminalConnected(true);
        }
        setTimeout(() => {
          if (terminalSocket && terminalSocket.readyState === WebSocket.OPEN) {
            terminalSocket.send(cmd + '\r');
            if (terminalInstance) terminalInstance.focus();
          }
        }, 250);
        return;
      }
      terminalSocket.send(cmd + '\r');
      if (terminalInstance) terminalInstance.focus();
    }

    function clearTerminalScreen() {
      if (terminalInstance) {
        terminalInstance.clear();
        terminalInstance.focus();
      }
    }
