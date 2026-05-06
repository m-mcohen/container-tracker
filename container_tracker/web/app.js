  /* ─────────────────────────────────────────────────────────────────────
   * Bridge shim — thin async wrappers around window.pywebview.api.
   * All bridge calls go through this object. NEVER call
   * window.pywebview.api.* directly elsewhere — typos there fail
   * silently as TypeError without crossing the bridge to Python.
   * Centralizing here makes typos JS-side errors with useful names.
   * ──────────────────────────────────────────────────────────────────── */
  const Bridge = {
    async list_containers() { return await window.pywebview.api.list_containers(); },
    async get_container(no) { return await window.pywebview.api.get_container(no); },
    async get_settings()    { return await window.pywebview.api.get_settings(); },
    async save_settings(company_name, api_token) { return await window.pywebview.api.save_settings(company_name, api_token); },
    async refresh_all()     { return await window.pywebview.api.refresh_all(); },
    async refresh_one(cn)   { return await window.pywebview.api.refresh_one(cn); },
    async add_container(cn, carrier) { return await window.pywebview.api.add_container(cn, carrier); },
    async remove_container(cn) { return await window.pywebview.api.remove_container(cn); },
    async archive_container(cn) { return await window.pywebview.api.archive_container(cn); },
    async restore_container(cn) { return await window.pywebview.api.restore_container(cn); },
    async list_carriers()   { return await window.pywebview.api.list_carriers(); },
    async set_excel_path(p) { return await window.pywebview.api.set_excel_path(p); },
    async create_excel_template(p) { return await window.pywebview.api.create_excel_template(p); },
    async pick_excel_file() { return await window.pywebview.api.pick_excel_file(); },
    async pick_excel_save_path() { return await window.pywebview.api.pick_excel_save_path(); },
    async open_linked_excel() { return await window.pywebview.api.open_linked_excel(); },
    async register_unmatched(items) { return await window.pywebview.api.register_unmatched(items); },
    async dismiss_unmatched(cns) { return await window.pywebview.api.dismiss_unmatched(cns); },
    async ping()            { return await window.pywebview.api.ping(); },
  };

  /* ─────────────────────────────────────────────────────────────────────
   * Error / info toasts. Single dismissible toast variant — Step 7 may
   * elaborate. Auto-dismiss after 8s; click to dismiss earlier. Falls
   * back to console if #toast-container is missing.
   * ──────────────────────────────────────────────────────────────────── */
  function _showToast(message, variant) {
    const container = document.getElementById("toast-container");
    if (!container) {
      (variant === "error" ? console.error : console.log)("[toast]", message);
      return;
    }
    const t = document.createElement("div");
    t.className = `toast toast-${variant}`;
    t.textContent = message;
    let dismissed = false;
    const dismiss = () => {
      if (dismissed) return;
      dismissed = true;
      t.classList.add("toast-fade");
      setTimeout(() => t.remove(), 250);
    };
    t.addEventListener("click", dismiss);
    setTimeout(dismiss, 8000);
    container.appendChild(t);
  }
  function showError(message) { _showToast(message, "error"); }
  function showInfo(message)  { _showToast(message, "info"); }

  /* ─────────────────────────────────────────────────────────────────────
   * Excel-related banners (Step 6.5). Notice elements live in the
   * dashboard's notification stack; helpers toggle the [hidden] attr
   * and stash CN payloads on the element via dataset for later reads
   * by the click handlers.
   * ──────────────────────────────────────────────────────────────────── */
  function showUnmatchedBanner(cns) {
    const b = document.getElementById("notice-unmatched");
    if (!b) return;
    const titleEl = document.getElementById("notice-unmatched-title");
    if (titleEl) {
      const n = cns.length;
      titleEl.textContent = `${n} new container${n === 1 ? "" : "s"} found in your spreadsheet.`;
    }
    b.dataset.cns = cns.join(",");
    b.hidden = false;
  }
  function hideUnmatchedBanner() {
    const b = document.getElementById("notice-unmatched");
    if (!b) return;
    b.hidden = true;
    b.dataset.cns = "";
  }
  function showExcelWriteFailedBanner() {
    const b = document.getElementById("notice-excel-write-failed");
    if (b) b.hidden = false;
  }
  function hideExcelWriteFailedBanner() {
    const b = document.getElementById("notice-excel-write-failed");
    if (b) b.hidden = true;
  }
  function showExcelMissingBanner() {
    const b = document.getElementById("notice-excel-missing");
    if (b) b.hidden = false;
  }
  function hideExcelMissingBanner() {
    const b = document.getElementById("notice-excel-missing");
    if (b) b.hidden = true;
  }

  /* Carrier dropdown options come from the bridge once at boot, then
   * cached. Keeps the register-unmatched modal in sync with CARRIER_NAMES
   * without baking the list into JS. */
  let CARRIERS = [];

  /* ─────────────────────────────────────────────────────────────────────
   * "Last refreshed" indicator. Driven by the time the user clicks
   * refresh, NOT by max(per-row last_refreshed). The user-facing
   * question is "when did I last hit refresh", not "how fresh is the
   * stalest container". Per-row r.last_refreshed lives on rows for
   * future per-row UI but does not feed this indicator.
   * ──────────────────────────────────────────────────────────────────── */
  let LAST_REFRESH_AT = null;
  function markRefreshed() {
    LAST_REFRESH_AT = Date.now();
    updateLastRefresh();
  }
  // Single relative-time formatter for both the session-level refresh
  // timestamp (millis from Date.now()) and per-row last_refreshed (ISO
  // string). Callers must convert to millis at the boundary.
  function formatRelativeMs(ms) {
    if (!Number.isFinite(ms)) return "—";
    const diffMin = Math.max(0, Math.round((Date.now() - ms) / 60000));
    return diffMin < 1 ? "just now" : `${diffMin} min ago`;
  }
  function parseIsoMs(iso) {
    if (!iso) return NaN;
    const t = Date.parse(iso);
    return Number.isFinite(t) ? t : NaN;
  }
  function updateLastRefresh() {
    const el = document.getElementById("last-refresh");
    if (!el) return;
    el.textContent = formatRelativeMs(LAST_REFRESH_AT);
  }
  // Keep the indicator roughly current if the user leaves the app idle.
  setInterval(updateLastRefresh, 30000);

  /* ─────────────────────────────────────────────────────────────────────
   * Live container data. Filled by loadInitialData() on pywebviewready;
   * empty until then. Reassignable (let, not const) because each refresh
   * replaces the whole array reference rather than mutating it — the
   * render code reads ROWS by closure, so reassignment propagates
   * without subscriber wiring.
   * ──────────────────────────────────────────────────────────────────── */
  let ROWS = [];

  // Status → CSS chip class. Lookup dict + one overlay rule for the
  // delayed-while-sailing case (a SAILING voyage with positive delay
  // renders as "delayed" so it stands out in the table).
  // Unknown statuses fall through to "untracked" (neutral gray).
  const STATUS_TO_CLASS = {
    SAILING:    "sailing",
    ARRIVED:    "arrived",
    DISCHARGED: "discharged",
    DELIVERED:  "delivered",
    GATE_OUT:   "gateout",
    BOOKED:     "booked",
  };
  function statusClass(row) {
    const s = (row.status || "").toUpperCase();
    if (s === "SAILING" && row.delayVal > 0) return "delayed";
    return STATUS_TO_CLASS[s] || "untracked";
  }
  function statusLabel(row) {
    const cls = statusClass(row);
    return { sailing:"Sailing", arrived:"Arrived", discharged:"Discharged",
             delivered:"Delivered", gateout:"Gate out", booked:"Booked",
             delayed:"Delayed", untracked:"—" }[cls];
  }

  // Sort: bucket priority — DELAYED < SAILING < ARRIVED < other (matches v1 StatusBucketSortProxy)
  function rank(row) {
    const c = statusClass(row);
    return { delayed:0, sailing:1, arrived:2, discharged:2, gateout:2, delivered:3, booked:4, untracked:5 }[c] ?? 5;
  }

  const TBODY = document.getElementById("shipments-tbody");

  let activeFilter = "all";

  // Set of CNs currently checked in the table. Persists across renders
  // so filtering / refresh doesn't blow away the user's selection. The
  // bulk-archive flow reads this and the change handlers below mutate it.
  const SELECTED = new Set();

  // Setting helper used by renderStats.
  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  // Recompute header / KPI / chip-count / footer-total from ROWS.
  // "Delayed" cross-cuts other buckets — a SAILING row with delayVal>0
  // counts in both Sailing and Delayed. Matches statusClass() semantics.
  // Three of four KPI subtitles are intentionally blank for now; only
  // kpi-tracked-sub ("Across N carriers") is wired.
  function renderStats() {
    // Archived rows are excluded from every count except their own chip
    // — "All" means "all live" by spec.
    const live = ROWS.filter(r => !r.archived);
    const total = live.length;
    const archivedCount = ROWS.length - total;
    // SAILING and DELAYED are mutually exclusive on the dashboard:
    // a SAILING row with a positive delay shows up only in DELAYED.
    // Matches statusClass()'s "delayed overlay" rule so the cards and
    // the chip filter agree on every row's bucket.
    // `> 0` is load-bearing: Number(null) coerces to 0 and Number(undefined) to NaN,
    // both of which fail `> 0` correctly. Switching to `>= 0` would count nulls as delayed.
    const delayed = live.filter(r => r.status === "SAILING" && Number(r.delayVal) > 0).length;
    const sailing = live.filter(r => r.status === "SAILING" && !(Number(r.delayVal) > 0)).length;
    const arrived = live.filter(r => r.status === "ARRIVED" || r.status === "DISCHARGED").length;
    const booked  = live.filter(r => r.status === "BOOKED").length;

    setText("title-count", `· ${total} tracked`);

    setText("kpi-tracked", String(total));
    setText("kpi-sailing", String(sailing));
    setText("kpi-arrived", String(arrived));
    setText("kpi-delayed", String(delayed));

    const carriers = new Set(live.map(r => r.carrier).filter(Boolean)).size;
    setText("kpi-tracked-sub", carriers ? `Across ${carriers} carrier${carriers === 1 ? "" : "s"}` : "");
    setText("kpi-sailing-sub", "");
    setText("kpi-arrived-sub", "");
    setText("kpi-delayed-sub", "");

    setText("chip-count-all", String(total));
    setText("chip-count-delayed", String(delayed));
    setText("chip-count-sailing", String(sailing));
    setText("chip-count-arrived", String(arrived));
    setText("chip-count-booked", String(booked));
    setText("chip-count-archived", String(archivedCount));

    setText("row-total", String(total));
  }

  function render() {
    renderStats();
    const q = (document.getElementById("search").value || "").toUpperCase();
    const filtered = ROWS
      .filter(r => {
        const isArchived = r.archived === true;
        // Archived view shows ONLY archived; every other view excludes them.
        if (activeFilter === "archived") return isArchived;
        if (isArchived) return false;
        if (activeFilter === "delayed") return statusClass(r) === "delayed";
        if (activeFilter === "sailing") return statusClass(r) === "sailing";
        if (activeFilter === "arrived") return ["arrived","discharged","gateout","delivered"].includes(statusClass(r));
        if (activeFilter === "booked")  return statusClass(r) === "booked";
        return true;
      })
      .filter(r => !q || (r.cn + r.vessel + r.pol + r.pod + r.carrier).toUpperCase().includes(q))
      .sort((a, b) => rank(a) - rank(b) || a.cn.localeCompare(b.cn));

    TBODY.innerHTML = filtered.map(r => {
      const isArchived = r.archived === true;
      const cls = isArchived ? "archived" : statusClass(r);
      const delayCls =
        r.delayVal > 0 ? "delay-pos" :
        r.delayVal < 0 ? "delay-neg" : "delay-neutral";

      const pctHtml = r.pct === null
        ? `<span class="muted">Not yet sailed</span>`
        : `<div class="transit">
             <div class="transit-bar"><div class="transit-fill ${cls}" style="width:${r.pct}%;"></div></div>
             <span class="transit-pct">${r.pct}%</span>
           </div>`;

      const routeHtml = !r.pol
        ? `<span class="muted">—</span>`
        : `<span class="route"><span>${r.pol}</span><span class="arrow">→</span><span>${r.pod}</span></span>`;

      const statusBadge = isArchived
        ? `<span class="chip-status archived"><span class="dot"></span>Archived</span>`
        : `<span class="chip-status ${cls}"><span class="dot"></span>${statusLabel(r)}</span>`;

      const actionsCell = isArchived
        ? `<button class="row-action-restore" type="button" data-action="restore" data-cn="${r.cn}">Restore</button>`
        : `<div class="row-actions">
             <button class="row-action" type="button" data-action="refresh" data-cn="${r.cn}" title="Refresh this container">
               <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M2 8a6 6 0 0 1 10.5-4M14 8a6 6 0 0 1-10.5 4"/><path d="M12 1.5v3h-3M4 14.5v-3h3"/></svg>
             </button>
             <button class="row-action" type="button" data-action="more" data-cn="${r.cn}" title="More actions">
               <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="3" cy="8" r=".9"/><circle cx="8" cy="8" r=".9"/><circle cx="13" cy="8" r=".9"/></svg>
             </button>
           </div>`;

      const checkAttr = SELECTED.has(r.cn) ? " checked" : "";
      const trClass   = isArchived ? "is-archived" : "";

      return `
        <tr data-cn="${r.cn}"${trClass ? ` class="${trClass}"` : ''}>
          <td class="col-check"><input type="checkbox" class="row-select" data-cn="${r.cn}" onclick="event.stopPropagation()"${checkAttr} /></td>
          <td><span class="cn">${r.cn}</span></td>
          <td>${r.carrier || '<span class="muted">—</span>'}</td>
          <td>${statusBadge}</td>
          <td class="col-num">${r.orig || '<span class="muted">—</span>'}</td>
          <td class="col-num">${r.eta  || '<span class="muted">—</span>'}</td>
          <td class="col-num"><span class="${delayCls}">${r.delay || '—'}</span></td>
          <td>${routeHtml}</td>
          <td>${r.vessel || '<span class="muted">—</span>'}</td>
          <td class="col-num">${pctHtml}</td>
          <td class="col-num">${actionsCell}</td>
        </tr>`;
    }).join("");

    document.getElementById("row-count").textContent = filtered.length;

    // Drop SELECTED entries that no longer exist in ROWS (refreshed
    // away). Filter changes clear SELECTED separately so archived
    // selections don't bleed into non-archived views.
    const knownCns = new Set(ROWS.map(r => r.cn));
    for (const cn of [...SELECTED]) {
      if (!knownCns.has(cn)) SELECTED.delete(cn);
    }
    updateBulkBar();
  }
  // Initial render with empty ROWS — pywebviewready will trigger a real load.
  render();

  /* ─── Initial data load (replaces Step 3's static-ROWS render) ──────── */
  async function loadInitialData() {
    try {
      ROWS = await Bridge.list_containers();
      render();
    } catch (e) {
      showError(`Failed to load containers: ${(e && e.message) || e}`);
    }
    try {
      await loadSettings();
    } catch (e) {
      // Settings load isn't fatal — log and continue.
      console.warn('[bridge] get_settings failed', e);
    }
    try {
      // Cache the carrier list once. The register-unmatched modal builds
      // its dropdowns from this; the add modal's options are baked in HTML
      // so it doesn't need this list (yet).
      CARRIERS = await Bridge.list_carriers();
    } catch (e) {
      console.warn('[bridge] list_carriers failed', e);
    }
    updateLastRefresh();
  }
  window.addEventListener('pywebviewready', loadInitialData);

  /* ─── Settings load/save ─── */
  async function loadSettings() {
    const s = await Bridge.get_settings();
    const companyEl = document.getElementById("settings-company");
    if (companyEl) companyEl.value = s.company_name || "";
    const tokInput = document.getElementById("settings-token");
    const tokVisible = document.getElementById("settings-token-visible");
    // Always blank — token never crosses the bridge to JS. Placeholder
    // signals "already set, leave blank to keep" vs. "not set yet".
    const placeholder = s.api_token_present
      ? "••••••••••••••••"
      : "Enter your ShipsGo API key";
    if (tokInput) {
      tokInput.value = "";
      tokInput.placeholder = placeholder;
    }
    if (tokVisible) {
      tokVisible.value = "";
      tokVisible.placeholder = placeholder;
    }
    const excelEl = document.getElementById("excel-current-path");
    if (excelEl) excelEl.textContent = s.excel_path || "No file linked";
    // Toolbar Open-in-Excel button mirrors the linked-file state. Same
    // bridge call as the Settings card's "Open in Excel"; disabled when
    // nothing's linked.
    const toolbarOpenBtn = document.getElementById("btn-open-excel-toolbar");
    if (toolbarOpenBtn) {
      const linked = !!(s.excel_path && s.excel_path.length > 0);
      toolbarOpenBtn.disabled = !linked;
      toolbarOpenBtn.title = linked
        ? `Open ${s.excel_path}`
        : "Link an Excel file in Settings to enable";
    }
  }

  async function handleSaveSettings() {
    const company = (document.getElementById("settings-company") || {value:""}).value;
    const tokInput = document.getElementById("settings-token") || {value:""};
    const tokVal = tokInput.value;
    // Pass null when the user didn't type anything — bridge then leaves
    // keyring untouched (deliberate departure from the legacy GUI, which
    // disabled Save on blank token).
    const tokenArg = tokVal && tokVal.trim() ? tokVal : null;
    let result;
    try {
      result = await Bridge.save_settings(company, tokenArg);
    } catch (e) {
      showError(`Save failed: ${(e && e.message) || e}`);
      return;
    }
    if (!result.ok) {
      showError(`Save failed: ${result.error || "unknown"}`);
      return;
    }
    await loadSettings();
    showInfo("Settings saved.");
  }
  const saveBtn = document.getElementById("btn-settings-save");
  if (saveBtn) saveBtn.addEventListener("click", handleSaveSettings);

  const app = document.getElementById("app");

  /* ─── Modals ─── */
  // Modal open-state lives on #app, not on #modal-add. Toggle the parent class.
  function resetAddModal() {
    document.getElementById("f-cn").value = "";
    document.getElementById("f-carrier").selectedIndex = 0;
    const errEl = document.getElementById("add-error");
    if (errEl) { errEl.hidden = true; errEl.textContent = ""; }
  }
  document.getElementById("btn-open-add").addEventListener("click", () => {
    resetAddModal();
    app.classList.add("modal-add-open");
  });
  document.querySelectorAll("[data-close-modal]").forEach(b =>
    b.addEventListener("click", () => app.classList.remove("modal-add-open", "modal-register-open", "modal-archive-open", "modal-bulk-archive-open"))
  );
  ["modal-add", "modal-archive", "modal-bulk-archive"].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener("click", (e) => {
      if (e.target.id === id) app.classList.remove("modal-add-open", "modal-archive-open", "modal-bulk-archive-open");
    });
  });

  /* ─── Add submit ─── */
  async function handleAddSubmit() {
    const cn = document.getElementById("f-cn").value.trim();
    const carrier = document.getElementById("f-carrier").value.trim();
    const errEl = document.getElementById("add-error");
    errEl.hidden = true;
    errEl.textContent = "";

    let result;
    try {
      result = await Bridge.add_container(cn, carrier);
    } catch (e) {
      errEl.textContent = `Add failed: ${(e && e.message) || e}`;
      errEl.hidden = false;
      return;
    }

    if (!result.ok) {
      if (result.error === "NOT_ENOUGH_CREDITS") {
        // Out-of-credits is global — close modal, show toast.
        app.classList.remove("modal-add-open");
        showError("ShipsGo: not enough credits to add this container.");
      } else if (result.error === "already_exists_local") {
        errEl.textContent = "Container is already tracked.";
        errEl.hidden = false;
      } else {
        errEl.textContent = result.error || "Failed to add container.";
        errEl.hidden = false;
      }
      return;
    }
    ROWS.push(result.container);
    render();
    app.classList.remove("modal-add-open");
    resetAddModal();
    if (result.was_existing) {
      showInfo("Already on ShipsGo — added to your dashboard.");
    }
    if (result.excel_write_failed) {
      showExcelWriteFailedBanner();
    }
  }
  document.getElementById("btn-add-submit").addEventListener("click", handleAddSubmit);

  /* ─── View routing — brand + gear button + Cancel/back all use [data-view] ─── */
  function showView(name) {
    document.querySelectorAll(".view").forEach(x => x.classList.remove("is-active"));
    const el = document.getElementById("view-" + name);
    if (el) el.classList.add("is-active");
    window.scrollTo({ top: 0, behavior: "instant" });
  }
  document.querySelectorAll("[data-view]").forEach(el => {
    el.addEventListener("click", (e) => {
      e.preventDefault();
      showView(el.dataset.view);
    });
  });

  /* ─── Settings: API-key Show / Test buttons ─── */
  // WebView2 blocks dynamic type-attribute changes on password inputs
  // for security, so toggling input.type fails silently. The fix is to
  // render two parallel inputs (one masked, one plain) and swap their
  // visibility. Two-way input listeners keep their values in lockstep
  // so handleSaveSettings can read whichever the user typed in.
  const tokenMasked = document.getElementById("settings-token");
  const tokenVisible = document.getElementById("settings-token-visible");
  if (tokenMasked && tokenVisible) {
    tokenMasked.addEventListener("input", () => { tokenVisible.value = tokenMasked.value; });
    tokenVisible.addEventListener("input", () => { tokenMasked.value = tokenVisible.value; });
  }
  const tokenShowBtn = document.getElementById("btn-token-show");
  if (tokenShowBtn) {
    tokenShowBtn.addEventListener("click", () => {
      if (!tokenMasked || !tokenVisible) return;
      const showing = !tokenVisible.hidden;
      if (showing) {
        tokenMasked.value = tokenVisible.value;
        tokenVisible.hidden = true;
        tokenMasked.hidden = false;
        tokenShowBtn.textContent = "Show";
      } else {
        tokenVisible.value = tokenMasked.value;
        tokenMasked.hidden = true;
        tokenVisible.hidden = false;
        tokenShowBtn.textContent = "Hide";
      }
    });
  }
  const shipsgoLink = document.getElementById("link-shipsgo");
  if (shipsgoLink) {
    shipsgoLink.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      window.open("https://shipsgo.com", "_blank");
    });
  }
  const tokenTestBtn = document.getElementById("btn-token-test");
  if (tokenTestBtn) {
    tokenTestBtn.addEventListener("click", async () => {
      // refresh_all is the only existing bridge call that exercises
      // the saved token against ShipsGo. Side effect: triggers the
      // same data-sync as the Refresh button. Acceptable for a manual
      // smoke-test action; a dedicated test_api_token shim would be
      // cleaner but lives outside this UI-only fix scope.
      const original = tokenTestBtn.textContent;
      tokenTestBtn.disabled = true;
      tokenTestBtn.textContent = "Testing…";
      let result;
      try {
        result = await Bridge.refresh_all();
      } catch (e) {
        showError(`API key test failed: ${(e && e.message) || e}`);
        tokenTestBtn.disabled = false;
        tokenTestBtn.textContent = original;
        return;
      }
      tokenTestBtn.disabled = false;
      tokenTestBtn.textContent = original;
      if (result && result.error) {
        showError(`API key test failed: ${result.error}`);
        return;
      }
      // No error from refresh_all means the token authenticated (or
      // there was nothing to refresh, which is also fine on a fresh
      // setup). Pull the fresh ROWS so the dashboard reflects the run.
      try {
        ROWS = await Bridge.list_containers();
        render();
        markRefreshed();
      } catch (_e) { /* non-fatal */ }
      showInfo("API key valid.");
    });
  }

  /* ─── Filter chips ─── */
  document.querySelectorAll(".toolbar .chip").forEach(c => {
    c.addEventListener("click", () => {
      activeFilter = c.dataset.filter;
      // Switching views resets the selection — bulk-archive vs.
      // bulk-restore depends on activeFilter, so carrying selections
      // across the boundary would be ambiguous.
      SELECTED.clear();
      document.querySelectorAll(".toolbar .chip").forEach(x => {
        const match = x.dataset.filter === activeFilter;
        x.classList.toggle("is-active", match);
        x.setAttribute("aria-pressed", match ? "true" : "false");
      });
      render();
    });
  });

  /* ─── Search ─── */
  document.getElementById("search").addEventListener("input", render);

  /* ─── Theme switch ─── */
  function setTheme(dark) {
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
    const sw = document.getElementById("theme-switch");
    if (sw) sw.setAttribute("aria-checked", dark ? "true" : "false");
    const cb = document.getElementById("dark-toggle-settings");
    if (cb) cb.checked = !!dark;
    try { localStorage.setItem("ct.theme", dark ? "dark" : "light"); } catch (e) {}
  }
  (function restoreTheme() {
    try {
      const saved = localStorage.getItem("ct.theme");
      if (saved === "dark" || saved === "light") setTheme(saved === "dark");
    } catch (e) {}
  })();
  document.getElementById("theme-switch")?.addEventListener("click", () => {
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    setTheme(!isDark);
  });
  const dts = document.getElementById("dark-toggle-settings");
  if (dts) dts.addEventListener("change", e => setTheme(e.target.checked));

  /* ─── Activity panel collapse ─── */
  document.getElementById("activity-toggle").addEventListener("click", () => {
    const panel = document.getElementById("activity-panel");
    const wasCollapsed = panel.classList.contains("is-collapsed");
    panel.classList.toggle("is-collapsed");
    document.getElementById("activity-toggle").setAttribute("aria-expanded", wasCollapsed ? "true" : "false");
  });

  /* ─── Refresh: live ShipsGo call via bridge ─── */
  async function handleRefresh() {
    const btn = document.getElementById("btn-refresh");
    const svg = btn.querySelector("svg");
    btn.disabled = true;
    btn.classList.add("is-loading");
    svg.style.transition = "transform .8s linear";
    svg.style.transform = "rotate(540deg)";
    try {
      const result = await Bridge.refresh_all();
      if (result.error) {
        showError(`Refresh failed: ${result.error}`);
      } else {
        ROWS = await Bridge.list_containers();
        render();
        markRefreshed();
        if (result.failed && result.failed.length > 0) {
          showError(`Refreshed ${result.updated} containers; ${result.failed.length} failed. See console.`);
          console.warn("[refresh] failed:", result.failed);
        }
        // Step 6.5: Excel-related result fields. Read failures don't abort
        // the data sync — surface as toast. Write failures get a banner
        // so the user knows the next refresh needs Excel closed.
        if (result.excel_read_failed) {
          showError("Couldn't read Excel — close it and click Refresh to sync the container list.");
        }
        if (result.excel_missing) {
          showExcelMissingBanner();
        } else {
          hideExcelMissingBanner();
        }
        if (result.excel_write_failed) {
          showExcelWriteFailedBanner();
        } else {
          hideExcelWriteFailedBanner();
        }
        const unmatched = result.unmatched || [];
        if (unmatched.length > 0) {
          showUnmatchedBanner(unmatched);
        } else {
          hideUnmatchedBanner();
        }
      }
    } catch (e) {
      showError(`Refresh failed: ${(e && e.message) || e}`);
    } finally {
      btn.disabled = false;
      btn.classList.remove("is-loading");
      setTimeout(() => { svg.style.transform = "rotate(0)"; }, 50);
    }
  }
  document.getElementById("btn-refresh").addEventListener("click", handleRefresh);

  /* ─── Keyboard shortcuts ─── */
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      app.classList.remove("modal-add-open", "modal-register-open", "modal-archive-open", "modal-bulk-archive-open");
      closeRowMenu();
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      document.getElementById("search").focus();
      document.getElementById("search").select();
    }
  });

  /* Banner dismiss (update banner only — destructive remove is fine
   * here because update-banner is only shown once per session). */
  document.querySelectorAll(".banner .dismiss").forEach(b =>
    b.addEventListener("click", () => b.closest(".banner").remove())
  );

  /* Excel-write-failed dismiss is non-destructive — the banner re-shows
   * on next refresh if the condition recurs. */
  const excelDismissBtn = document.getElementById("notice-excel-dismiss");
  if (excelDismissBtn) {
    excelDismissBtn.addEventListener("click", hideExcelWriteFailedBanner);
  }

  /* ─── Unmatched-CN flow (Step 6.5) ─── */
  function getUnmatchedCNs() {
    const banner = document.getElementById("notice-unmatched");
    if (!banner || banner.hidden) return [];
    return (banner.dataset.cns || "").split(",").filter(Boolean);
  }

  function openRegisterUnmatchedModal() {
    const cns = getUnmatchedCNs();
    if (cns.length === 0) return;
    const list = document.getElementById("register-unmatched-list");
    if (!list) return;
    const carriers = (CARRIERS && CARRIERS.length > 0)
      ? CARRIERS
      : ["MAERSK LINE", "MSC", "CMA CGM", "HAPAG LLOYD", "COSCO",
         "EVERGREEN", "ONE", "YANG MING", "ZIM", "HMM", "OOCL", "PIL", "OTHER"];
    list.innerHTML = cns.map(cn => {
      const opts = ['<option value="">Select carrier…</option>']
        .concat(carriers.map(c => `<option value="${c}">${c}</option>`))
        .join("");
      return `
        <div class="register-row">
          <span class="register-cn">${cn}</span>
          <select class="register-carrier" data-cn="${cn}">${opts}</select>
        </div>`;
    }).join("");
    const cost = document.getElementById("register-cost");
    if (cost) cost.textContent = String(cns.length);
    const errEl = document.getElementById("register-error");
    if (errEl) { errEl.hidden = true; errEl.textContent = ""; }
    app.classList.add("modal-register-open");
  }

  async function handleDismissUnmatched() {
    const cns = getUnmatchedCNs();
    if (cns.length === 0) return;
    let result;
    try {
      result = await Bridge.dismiss_unmatched(cns);
    } catch (e) {
      showError(`Dismiss failed: ${(e && e.message) || e}`);
      return;
    }
    if (!result.ok) {
      showError(`Dismiss failed: ${result.error || "unknown"}`);
      return;
    }
    hideUnmatchedBanner();
    showInfo(`Skipped ${cns.length} container${cns.length === 1 ? "" : "s"}. They won't appear again.`);
  }

  async function handleRegisterUnmatchedSubmit() {
    const errEl = document.getElementById("register-error");
    if (errEl) { errEl.hidden = true; errEl.textContent = ""; }
    const selects = document.querySelectorAll("#register-unmatched-list .register-carrier");
    const items = [];
    for (const s of selects) {
      if (!s.value) {
        if (errEl) {
          errEl.textContent = "Pick a carrier for every container, or click Cancel and use Skip.";
          errEl.hidden = false;
        }
        return;
      }
      items.push({ cn: s.dataset.cn, carrier: s.value });
    }
    let result;
    try {
      result = await Bridge.register_unmatched(items);
    } catch (e) {
      if (errEl) {
        errEl.textContent = `Register failed: ${(e && e.message) || e}`;
        errEl.hidden = false;
      }
      return;
    }
    app.classList.remove("modal-register-open");
    hideUnmatchedBanner();
    if (result.failed && result.failed.length > 0) {
      const credits = result.failed.find(f => f.error === "NOT_ENOUGH_CREDITS");
      if (credits) {
        showError("ShipsGo: not enough credits — registration stopped.");
      } else {
        showError(`Registered ${result.registered}; ${result.failed.length} failed. See console.`);
        console.warn("[register_unmatched] failed:", result.failed);
      }
    } else if (result.registered > 0) {
      showInfo(`Registered ${result.registered} container${result.registered === 1 ? "" : "s"}. Refreshing…`);
    }
    // Pull the fresh shipment data for newly-registered CNs.
    await handleRefresh();
  }

  const noticeRegisterBtn = document.getElementById("notice-register");
  if (noticeRegisterBtn) {
    noticeRegisterBtn.addEventListener("click", openRegisterUnmatchedModal);
  }
  const noticeSkipBtn = document.getElementById("notice-skip");
  if (noticeSkipBtn) {
    noticeSkipBtn.addEventListener("click", handleDismissUnmatched);
  }
  const registerSubmitBtn = document.getElementById("btn-register-submit");
  if (registerSubmitBtn) {
    registerSubmitBtn.addEventListener("click", handleRegisterUnmatchedSubmit);
  }
  // Backdrop / Cancel close — extend the existing modal close handlers.
  const registerModal = document.getElementById("modal-register-unmatched");
  if (registerModal) {
    registerModal.addEventListener("click", (e) => {
      if (e.target.id === "modal-register-unmatched") {
        app.classList.remove("modal-register-open");
      }
    });
  }

  /* ─── Settings: linked-spreadsheet card (Step 6.5) ─── */
  async function handleExcelBrowse() {
    let pick;
    try {
      pick = await Bridge.pick_excel_file();
    } catch (e) {
      showError(`Browse failed: ${(e && e.message) || e}`);
      return;
    }
    if (!pick || !pick.path) {
      // User cancelled; pick.error is null in that case. Real errors land
      // in pick.error and we surface them.
      if (pick && pick.error) showError(`Browse failed: ${pick.error}`);
      return;
    }
    let r;
    try {
      r = await Bridge.set_excel_path(pick.path);
    } catch (e) {
      showError(`Couldn't link file: ${(e && e.message) || e}`);
      return;
    }
    if (!r.ok) {
      showError(`Couldn't link file: ${r.error || "unknown"}`);
      return;
    }
    await loadSettings();
    showInfo("Excel file linked.");
  }

  async function handleExcelCreate() {
    let pick;
    try {
      pick = await Bridge.pick_excel_save_path();
    } catch (e) {
      showError(`Create template failed: ${(e && e.message) || e}`);
      return;
    }
    if (!pick || !pick.path) {
      if (pick && pick.error) showError(`Create template failed: ${pick.error}`);
      return;
    }
    let r;
    try {
      r = await Bridge.create_excel_template(pick.path);
    } catch (e) {
      showError(`Create template failed: ${(e && e.message) || e}`);
      return;
    }
    if (!r.ok) {
      showError(`Create template failed: ${r.error || "unknown"}`);
      return;
    }
    await loadSettings();
    showInfo("Template created and linked.");
  }

  async function handleExcelOpen() {
    let r;
    try {
      r = await Bridge.open_linked_excel();
    } catch (e) {
      showError(`Couldn't open file: ${(e && e.message) || e}`);
      return;
    }
    if (!r.ok) {
      showError(`Couldn't open file: ${r.error || "unknown"}`);
    }
  }

  const excelBrowseBtn = document.getElementById("btn-excel-browse");
  if (excelBrowseBtn) excelBrowseBtn.addEventListener("click", handleExcelBrowse);
  const excelCreateBtn = document.getElementById("btn-excel-create");
  if (excelCreateBtn) excelCreateBtn.addEventListener("click", handleExcelCreate);
  const excelOpenBtn = document.getElementById("btn-excel-open");
  if (excelOpenBtn) excelOpenBtn.addEventListener("click", handleExcelOpen);
  const toolbarOpenExcelBtn = document.getElementById("btn-open-excel-toolbar");
  if (toolbarOpenExcelBtn) toolbarOpenExcelBtn.addEventListener("click", handleExcelOpen);

  /* ─── Row action menu + archive flow ─── */
  // Position the menu next to the trigger button using viewport coords
  // (position: fixed in CSS). One global menu element for all rows.
  function openRowMenu(triggerBtn, cn) {
    const menu = document.getElementById("row-menu");
    if (!menu) return;
    const rect = triggerBtn.getBoundingClientRect();
    menu.style.top = `${rect.bottom + 4}px`;
    menu.style.left = `${Math.max(8, rect.right - 140)}px`;
    menu.dataset.cn = cn;
    menu.hidden = false;
  }
  function closeRowMenu() {
    const menu = document.getElementById("row-menu");
    if (!menu) return;
    menu.hidden = true;
    menu.dataset.cn = "";
  }

  TBODY.addEventListener("click", async (e) => {
    const refreshBtn = e.target.closest('[data-action="refresh"]');
    if (refreshBtn) {
      const cn = refreshBtn.dataset.cn;
      refreshBtn.disabled = true;
      refreshBtn.classList.add("is-loading");
      try {
        const res = await Bridge.refresh_one(cn);
        if (res?.error) _showToast(res.error, "err");
        else _showToast(`${cn} refreshed`, "ok");
        ROWS = await Bridge.list_containers();
        render();
      } finally {
        // row will be re-rendered, but if not:
        refreshBtn.disabled = false;
        refreshBtn.classList.remove("is-loading");
      }
      return;
    }

    const moreBtn = e.target.closest("[data-action='more']");
    if (moreBtn) {
      e.stopPropagation();
      openRowMenu(moreBtn, moreBtn.dataset.cn || "");
      return;
    }
    const restoreBtn = e.target.closest("[data-action='restore']");
    if (restoreBtn) {
      e.stopPropagation();
      handleSingleRestore(restoreBtn.dataset.cn || "");
      return;
    }
  });

  async function handleSingleRestore(cn) {
    if (!cn) return;
    let result;
    try {
      result = await Bridge.restore_container(cn);
    } catch (e) {
      showError(`Restore failed: ${(e && e.message) || e}`);
      return;
    }
    if (!result || !result.ok) {
      showError(`Restore failed: ${(result && result.error) || "unknown"}`);
      return;
    }
    const idx = ROWS.findIndex(r => r.cn === cn);
    if (idx >= 0) ROWS[idx] = Object.assign({}, ROWS[idx], { archived: false });
    SELECTED.delete(cn);
    render();
    if (result.excel_write_failed) showExcelWriteFailedBanner();
    showInfo("Container restored.");
  }

  const rowMenu = document.getElementById("row-menu");
  if (rowMenu) {
    rowMenu.addEventListener("click", (e) => {
      const item = e.target.closest("[data-action]");
      if (!item) return;
      const action = item.dataset.action;
      const cn = rowMenu.dataset.cn || "";
      closeRowMenu();
      if (action === "archive" && cn) openArchiveModal(cn);
    });
  }
  // Click anywhere else closes the menu. Capture phase so the menu
  // closes before any other handler runs.
  document.addEventListener("click", (e) => {
    const menu = document.getElementById("row-menu");
    if (!menu || menu.hidden) return;
    if (e.target.closest("#row-menu")) return;
    if (e.target.closest("[data-action='more']")) return;
    closeRowMenu();
  });

  function openArchiveModal(cn) {
    const cnEl = document.getElementById("archive-cn");
    if (cnEl) cnEl.textContent = cn;
    const modal = document.getElementById("modal-archive");
    if (modal) modal.dataset.cn = cn;
    app.classList.add("modal-archive-open");
  }

  async function handleArchiveConfirm() {
    const modal = document.getElementById("modal-archive");
    const cn = (modal && modal.dataset.cn) || "";
    if (!cn) {
      app.classList.remove("modal-archive-open");
      return;
    }
    app.classList.remove("modal-archive-open");
    let result;
    try {
      result = await Bridge.archive_container(cn);
    } catch (e) {
      showError(`Archive failed: ${(e && e.message) || e}`);
      return;
    }
    if (!result.ok) {
      showError(`Archive failed: ${result.error || "unknown"}`);
      return;
    }
    // Mark archived in ROWS rather than removing — the Archived view
    // needs to find it later. The render filter hides it from every
    // other view automatically.
    const idx = ROWS.findIndex(r => r.cn === cn);
    if (idx >= 0) ROWS[idx] = Object.assign({}, ROWS[idx], { archived: true });
    render();
    if (result.excel_write_failed) {
      showExcelWriteFailedBanner();
    }
    showInfo("Container archived.");
  }
  const archiveConfirmBtn = document.getElementById("btn-archive-confirm");
  if (archiveConfirmBtn) archiveConfirmBtn.addEventListener("click", handleArchiveConfirm);

  /* ─── Bulk selection + bulk archive / restore ─── */
  function updateBulkBar() {
    const bar = document.getElementById("bulk-bar");
    const countEl = document.getElementById("bulk-count");
    if (!bar) return;
    const n = SELECTED.size;
    bar.hidden = n === 0;
    if (countEl) countEl.textContent = `${n} container${n === 1 ? "" : "s"} selected`;
    // Toggle bulk action button: archive in any non-archived view,
    // restore in the archived view. SELECTED.clear() on filter change
    // means the bar is always empty when we hit a transition, so the
    // toggle never displays the wrong button against the wrong rows.
    const archiveBtn = document.getElementById("bulk-archive");
    const restoreBtn = document.getElementById("bulk-restore");
    const inArchivedView = activeFilter === "archived";
    if (archiveBtn) archiveBtn.hidden = inArchivedView;
    if (restoreBtn) restoreBtn.hidden = !inArchivedView;
    // Header checkbox tri-state — checked when every visible row is
    // selected, indeterminate when some are.
    const headerCb = document.querySelector("table.shipments thead input[type=checkbox]");
    if (headerCb) {
      const selectableRows = document.querySelectorAll(
        "#shipments-tbody input.row-select:not([disabled])");
      const total = selectableRows.length;
      const checked = Array.from(selectableRows).filter(cb => cb.checked).length;
      headerCb.checked = total > 0 && checked === total;
      headerCb.indeterminate = checked > 0 && checked < total;
    }
  }

  TBODY.addEventListener("change", (e) => {
    const cb = e.target.closest("input.row-select[data-cn]");
    if (!cb) return;
    const cn = cb.dataset.cn || "";
    if (!cn) return;
    if (cb.checked) SELECTED.add(cn);
    else SELECTED.delete(cn);
    updateBulkBar();
  });

  const headerCheckbox = document.querySelector("table.shipments thead input[type=checkbox]");
  if (headerCheckbox) {
    headerCheckbox.addEventListener("change", (e) => {
      const target = e.target.checked;
      // Operate only on currently-rendered, non-archived rows.
      document.querySelectorAll(
        "#shipments-tbody input.row-select[data-cn]:not([disabled])"
      ).forEach(cb => {
        cb.checked = target;
        const cn = cb.dataset.cn || "";
        if (!cn) return;
        if (target) SELECTED.add(cn);
        else SELECTED.delete(cn);
      });
      updateBulkBar();
    });
  }

  const bulkClearLink = document.getElementById("bulk-clear");
  if (bulkClearLink) {
    bulkClearLink.addEventListener("click", (e) => {
      e.preventDefault();
      SELECTED.clear();
      document.querySelectorAll(
        "#shipments-tbody input.row-select"
      ).forEach(cb => { cb.checked = false; });
      updateBulkBar();
    });
  }

  const bulkArchiveBtn = document.getElementById("bulk-archive");
  if (bulkArchiveBtn) {
    bulkArchiveBtn.addEventListener("click", () => {
      if (SELECTED.size === 0) return;
      const countEl = document.getElementById("bulk-archive-count");
      if (countEl) countEl.textContent = String(SELECTED.size);
      app.classList.add("modal-bulk-archive-open");
    });
  }

  async function handleBulkArchiveConfirm() {
    app.classList.remove("modal-bulk-archive-open");
    const cns = Array.from(SELECTED);
    if (cns.length === 0) return;
    let archived = 0;
    let excelFailed = false;
    let firstError = null;
    for (const cn of cns) {
      let result;
      try {
        result = await Bridge.archive_container(cn);
      } catch (e) {
        if (!firstError) firstError = (e && e.message) || String(e);
        continue;
      }
      if (!result || !result.ok) {
        if (!firstError && result && result.error) firstError = result.error;
        continue;
      }
      archived++;
      const idx = ROWS.findIndex(r => r.cn === cn);
      if (idx >= 0) ROWS[idx] = Object.assign({}, ROWS[idx], { archived: true });
      if (result.excel_write_failed) excelFailed = true;
    }
    SELECTED.clear();
    render();
    if (excelFailed) showExcelWriteFailedBanner();
    if (firstError && archived === 0) {
      showError(`Archive failed: ${firstError}`);
    } else {
      if (firstError) {
        console.warn("[bulk-archive] some failures:", firstError);
      }
      showInfo(`${archived} container${archived === 1 ? "" : "s"} archived.`);
    }
  }
  const bulkArchiveConfirmBtn = document.getElementById("btn-bulk-archive-confirm");
  if (bulkArchiveConfirmBtn) {
    bulkArchiveConfirmBtn.addEventListener("click", handleBulkArchiveConfirm);
  }

  async function handleBulkRestore() {
    const cns = Array.from(SELECTED);
    if (cns.length === 0) return;
    let restored = 0;
    let excelFailed = false;
    let firstError = null;
    for (const cn of cns) {
      let result;
      try {
        result = await Bridge.restore_container(cn);
      } catch (e) {
        if (!firstError) firstError = (e && e.message) || String(e);
        continue;
      }
      if (!result || !result.ok) {
        if (!firstError && result && result.error) firstError = result.error;
        continue;
      }
      restored++;
      const idx = ROWS.findIndex(r => r.cn === cn);
      if (idx >= 0) ROWS[idx] = Object.assign({}, ROWS[idx], { archived: false });
      if (result.excel_write_failed) excelFailed = true;
    }
    SELECTED.clear();
    render();
    if (excelFailed) showExcelWriteFailedBanner();
    if (firstError && restored === 0) {
      showError(`Restore failed: ${firstError}`);
    } else {
      if (firstError) console.warn("[bulk-restore] some failures:", firstError);
      showInfo(`${restored} container${restored === 1 ? "" : "s"} restored.`);
    }
  }
  const bulkRestoreBtn = document.getElementById("bulk-restore");
  if (bulkRestoreBtn) bulkRestoreBtn.addEventListener("click", handleBulkRestore);

