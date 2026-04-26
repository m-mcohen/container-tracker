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
   * drawer/render code reads ROWS by closure, so reassignment
   * propagates without subscriber wiring.
   * ──────────────────────────────────────────────────────────────────── */
  let ROWS = [];

  // Status → CSS chip class (mirrors v1 normalize_status logic)
  function statusClass(row) {
    const s = (row.status || "").toUpperCase();
    if (s === "SAILING" && row.delayVal > 0) return "delayed";
    if (s === "SAILING") return "sailing";
    if (s === "ARRIVED") return "arrived";
    if (s === "DISCHARGED") return "discharged";
    if (s === "DELIVERED") return "delivered";
    if (s === "GATE_OUT") return "gateout";
    if (s === "BOOKED") return "booked";
    return "untracked";
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

  // Setting helper used by renderStats + drawer.
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
    const total = ROWS.length;
    const sailing = ROWS.filter(r => r.status === "SAILING").length;
    const arrived = ROWS.filter(r => r.status === "ARRIVED" || r.status === "DISCHARGED").length;
    // `> 0` is load-bearing: Number(null) coerces to 0 and Number(undefined) to NaN,
    // both of which fail `> 0` correctly. Switching to `>= 0` would count nulls as delayed.
    const delayed = ROWS.filter(r => Number(r.delayVal) > 0).length;
    const booked  = ROWS.filter(r => r.status === "BOOKED").length;

    setText("title-count", `· ${total} tracked`);

    setText("kpi-tracked", String(total));
    setText("kpi-sailing", String(sailing));
    setText("kpi-arrived", String(arrived));
    setText("kpi-delayed", String(delayed));

    const carriers = new Set(ROWS.map(r => r.carrier).filter(Boolean)).size;
    setText("kpi-tracked-sub", carriers ? `Across ${carriers} carrier${carriers === 1 ? "" : "s"}` : "");
    setText("kpi-sailing-sub", "");
    setText("kpi-arrived-sub", "");
    setText("kpi-delayed-sub", "");

    setText("chip-count-all", String(total));
    setText("chip-count-delayed", String(delayed));
    setText("chip-count-sailing", String(sailing));
    setText("chip-count-arrived", String(arrived));
    setText("chip-count-booked", String(booked));

    setText("row-total", String(total));
  }

  function render() {
    renderStats();
    const q = (document.getElementById("search").value || "").toUpperCase();
    const filtered = ROWS
      .filter(r => {
        if (activeFilter === "delayed") return statusClass(r) === "delayed";
        if (activeFilter === "sailing") return statusClass(r) === "sailing";
        if (activeFilter === "arrived") return ["arrived","discharged","gateout","delivered"].includes(statusClass(r));
        if (activeFilter === "booked")  return statusClass(r) === "booked";
        return true;
      })
      .filter(r => !q || (r.cn + r.vessel + r.pol + r.pod + r.carrier).toUpperCase().includes(q))
      .sort((a, b) => rank(a) - rank(b) || a.cn.localeCompare(b.cn));

    TBODY.innerHTML = filtered.map(r => {
      const cls = statusClass(r);
      const delayCls = r.delayVal > 0 ? "delay-pos" : (r.delayVal < 0 ? "delay-neg" : "delay-neutral");
      const pctHtml = r.pct === null
        ? `<span class="muted" style="font-size:11px">Not yet sailed</span>`
        : `<div class="transit-bar"><div class="transit-fill ${cls}" style="width:${r.pct}%;"></div></div><div class="transit-pct">${r.pct}%</div>`;
      const routeHtml = !r.pol
        ? `<span class="muted">—</span>`
        : `<span class="route"><span>${r.pol}</span><span class="arrow">→</span><span>${r.pod}</span></span>`;
      return `
        <tr data-cn="${r.cn}">
          <td><input type="checkbox" aria-label="Select ${r.cn}" onclick="event.stopPropagation()" /></td>
          <td><span class="cn">${r.cn}</span></td>
          <td><span class="carrier"><span class="carrier-badge c-${r.scac}">${r.scac}</span>${r.carrier}</span></td>
          <td><span class="chip-status ${cls}"><span class="dot"></span>${statusLabel(r)}</span></td>
          <td>${r.orig || '<span class="muted">—</span>'}</td>
          <td>${r.eta || '<span class="muted">—</span>'}</td>
          <td><span class="${delayCls}">${r.delay || '—'}</span></td>
          <td>${routeHtml}</td>
          <td>${r.vessel || '<span class="muted">—</span>'}</td>
          <td><div class="transit">${pctHtml}</div></td>
          <td>
            <div class="row-actions">
              <button class="row-action" aria-label="Refresh ${r.cn}" title="Refresh"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/></svg></button>
              <button class="row-action" aria-label="More actions for ${r.cn}" title="More"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="5" cy="12" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="19" cy="12" r="1.4"/></svg></button>
            </div>
          </td>
        </tr>`;
    }).join("");

    document.getElementById("row-count").textContent = filtered.length;
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
    if (tokInput) {
      // Always blank — token never crosses the bridge to JS. Placeholder
      // signals "already set, leave blank to keep" vs. "not set yet".
      tokInput.value = "";
      tokInput.placeholder = s.api_token_present
        ? "••••••••••••••••"
        : "Enter your ShipsGo API key";
    }
    const excelEl = document.getElementById("excel-current-path");
    if (excelEl) excelEl.textContent = s.excel_path || "No file linked";
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

  /* ─── Drawer ─── */
  const app = document.getElementById("app");
  // Track which cn the drawer / remove-modal is currently acting on so
  // the remove-confirm handler doesn't have to re-derive it from DOM.
  let DRAWER_CN = null;
  TBODY.addEventListener("click", (e) => {
    const tr = e.target.closest("tr");
    if (!tr) return;
    const row = ROWS.find(r => r.cn === tr.dataset.cn);
    if (!row) return;
    DRAWER_CN = row.cn;
    const cls = statusClass(row);
    document.getElementById("drawer-title").textContent = row.cn;
    document.getElementById("drawer-sub").textContent = `${row.carrier} · ${row.vessel || "No vessel yet"}`;
    const status = document.getElementById("drawer-status");
    status.className = `chip-status ${cls}`;
    status.innerHTML = `<span class="dot"></span>${statusLabel(row)}`;
    const delay = document.getElementById("drawer-delay");
    if (row.delayVal > 0) { delay.style.color = "var(--status-delayed)"; delay.textContent = `${row.delay} late`; }
    else if (row.delayVal < 0) { delay.style.color = "var(--status-arrived)"; delay.textContent = `${row.delay} early`; }
    else if (row.delayVal === 0) { delay.style.color = "var(--text-secondary)"; delay.textContent = "On time"; }
    else { delay.style.color = "var(--text-hint)"; delay.textContent = "Not yet sailed"; }
    const fill = document.getElementById("drawer-fill");
    const pct  = document.getElementById("drawer-pct");
    if (row.pct === null) { fill.style.width = "0%"; pct.textContent = "—"; }
    else { fill.style.width = row.pct + "%"; fill.className = `transit-fill ${cls}`; pct.textContent = row.pct + "%"; }
    document.getElementById("drawer-cn").textContent = row.cn;
    setText("drawer-last-refresh", formatRelativeMs(parseIsoMs(row.last_refreshed)));
    app.classList.add("drawer-open");
  });
  document.getElementById("drawer-close").addEventListener("click", () => app.classList.remove("drawer-open"));
  document.getElementById("drawer-backdrop").addEventListener("click", () => app.classList.remove("drawer-open"));
  document.getElementById("drawer-remove").addEventListener("click", () => {
    document.getElementById("remove-cn").textContent = document.getElementById("drawer-cn").textContent;
    app.classList.remove("drawer-open");
    app.classList.add("modal-remove-open");
  });

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
    b.addEventListener("click", () => app.classList.remove("modal-add-open", "modal-remove-open", "modal-register-open"))
  );
  ["modal-add", "modal-remove"].forEach(id => {
    document.getElementById(id).addEventListener("click", (e) => {
      if (e.target.id === id) app.classList.remove("modal-add-open", "modal-remove-open");
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
  }
  document.getElementById("btn-add-submit").addEventListener("click", handleAddSubmit);

  /* ─── Remove confirm ─── */
  async function handleRemoveConfirm() {
    if (!DRAWER_CN) {
      app.classList.remove("modal-remove-open");
      return;
    }
    const cn = DRAWER_CN;
    let result;
    try {
      result = await Bridge.remove_container(cn);
    } catch (e) {
      showError(`Remove failed: ${(e && e.message) || e}`);
      return;
    }
    if (!result.ok) {
      showError(`Remove failed: ${result.error || "unknown"}`);
      return;
    }
    ROWS = ROWS.filter(r => r.cn !== cn);
    DRAWER_CN = null;
    render();
    app.classList.remove("modal-remove-open", "drawer-open");
  }
  document.getElementById("btn-remove-confirm").addEventListener("click", handleRemoveConfirm);

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

  /* ─── Settings nav (highlight section + smooth scroll) ─── */
  document.querySelectorAll(".settings-nav a").forEach(a => {
    a.addEventListener("click", () => {
      document.querySelectorAll(".settings-nav a").forEach(x => x.classList.remove("is-active"));
      a.classList.add("is-active");
    });
  });

  /* ─── Filter chips ─── */
  document.querySelectorAll(".toolbar .chip").forEach(c => {
    c.addEventListener("click", () => {
      activeFilter = c.dataset.filter;
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
  }
  document.getElementById("theme-switch").addEventListener("click", () => {
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
      app.classList.remove("drawer-open", "modal-add-open", "modal-remove-open", "modal-register-open");
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

