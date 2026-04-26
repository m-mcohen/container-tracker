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
    async ping()            { return await window.pywebview.api.ping(); },
  };

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

  function render() {
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
      // Step 6 will add UI for this; for now console.error is the contract.
      console.error('[bridge] list_containers failed', e);
    }
  }
  window.addEventListener('pywebviewready', loadInitialData);

  /* ─── Drawer ─── */
  const app = document.getElementById("app");
  TBODY.addEventListener("click", (e) => {
    const tr = e.target.closest("tr");
    if (!tr) return;
    const row = ROWS.find(r => r.cn === tr.dataset.cn);
    if (!row) return;
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
  document.getElementById("btn-open-add").addEventListener("click", () => app.classList.add("modal-add-open"));
  document.querySelectorAll("[data-close-modal]").forEach(b =>
    b.addEventListener("click", () => app.classList.remove("modal-add-open", "modal-remove-open"))
  );
  ["modal-add", "modal-remove"].forEach(id => {
    document.getElementById(id).addEventListener("click", (e) => {
      if (e.target.id === id) app.classList.remove("modal-add-open", "modal-remove-open");
    });
  });

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

  /* ─── Refresh: spin + update timestamp ─── */
  document.getElementById("btn-refresh").addEventListener("click", () => {
    const btn = document.getElementById("btn-refresh");
    const svg = btn.querySelector("svg");
    svg.style.transition = "transform .8s ease";
    svg.style.transform = "rotate(540deg)";
    setTimeout(() => { svg.style.transform = "rotate(0)"; }, 850);
    document.getElementById("last-refresh").textContent = "just now";
  });

  /* ─── Keyboard shortcuts ─── */
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      app.classList.remove("drawer-open", "modal-add-open", "modal-remove-open");
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      document.getElementById("search").focus();
      document.getElementById("search").select();
    }
  });

  /* Banner dismiss */
  document.querySelectorAll(".banner .dismiss").forEach(b =>
    b.addEventListener("click", () => b.closest(".banner").remove())
  );

  /* Notice dismiss (skip / register buttons both clear the notice for the demo) */
  document.querySelectorAll("#notice-unmatched .btn-sm").forEach(b =>
    b.addEventListener("click", () => document.getElementById("notice-unmatched").remove())
  );

