/* KVI School Intelligence dashboard.
 * Security: every value that originates from imported messages, posts or
 * reports is passed through esc() before insertion. The server enforces roles;
 * the UI only hides controls the user cannot use. */
(() => {
  "use strict";

  const ROLE_RANK = { viewer: 0, staff: 1, leadership: 2, admin: 3 };
  const PAGES = [
    { group: "Overview", items: [["overview", "Dashboard overview", "staff"]] },
    { group: "Sources", items: [
      ["sources", "Source connections", "staff"],
      ["groups", "WhatsApp group registry", "staff"],
      ["facebook", "Facebook Page", "staff"]] },
    { group: "Reports", items: [
      ["reports", "Daily reports", "leadership"],
      ["classes", "Class-wise insights", "leadership"],
      ["educators", "Educator coordination", "leadership"],
      ["parents", "Parent concerns", "leadership"],
      ["alerts", "Alerts & action tracker", "leadership"],
      ["archive", "Communication archive", "staff"],
      ["email", "Email delivery logs", "leadership"]] },
    { group: "Administration", items: [
      ["scheduler", "Scheduler settings", "staff"],
      ["privacy", "Privacy & retention", "admin"],
      ["users", "User management", "admin"],
      ["system", "System health", "leadership"]] },
  ];

  const state = { user: null, meta: null, today: null };
  const $ = (sel) => document.querySelector(sel);
  const content = () => $("#content");

  // ------------------------------------------------------------ utilities
  function esc(v) {
    if (v === null || v === undefined) return "";
    return String(v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  const na = (v) => (v === null || v === undefined || v === "" ? "n/a" : esc(v));
  const can = (role) => state.user && ROLE_RANK[state.user.role] >= ROLE_RANK[role];

  function toast(msg, ms = 4000) {
    const t = $("#toast");
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => (t.hidden = true), ms);
  }

  async function api(method, path, body, { form = false, raw = false } = {}) {
    const headers = { "X-Requested-With": "kvi-dashboard", Accept: "application/json" };
    let payload;
    if (body !== undefined && body !== null) {
      if (form) payload = body;
      else { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
    }
    const res = await fetch(path, { method, headers, body: payload, credentials: "same-origin" });
    if (res.status === 401 && path !== "/api/auth/login") { showLogin("Your session has ended. Please sign in again."); throw new Error("401"); }
    if (raw) { if (!res.ok) throw new Error(`HTTP ${res.status}`); return res; }
    let data = null;
    try { data = await res.json(); } catch (_) { /* no body */ }
    if (!res.ok) {
      const detail = data && data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : `HTTP ${res.status}`;
      throw new Error(detail);
    }
    return data;
  }

  function chip(p) {
    const k = (p || "UNKNOWN").toUpperCase();
    return `<span class="chip ${esc(k)}">${esc(k)}</span>`;
  }
  function statusChip(text, kind) { return `<span class="chip ${esc(kind || "neutral")}">${esc(text)}</span>`; }
  function fmtDate(v) { return v ? esc(v) : '<span class="muted">never</span>'; }

  function confirmDialog(title, bodyHtml, okLabel = "Confirm", danger = false) {
    return new Promise((resolve) => {
      const modal = $("#modal");
      $("#modal-title").textContent = title;
      $("#modal-body").innerHTML = bodyHtml;
      const ok = $("#modal-ok");
      ok.textContent = okLabel;
      ok.className = "btn " + (danger ? "danger" : "primary");
      modal.hidden = false;
      ok.focus();
      const done = (val) => {
        modal.hidden = true;
        ok.onclick = null;
        $("#modal-cancel").onclick = null;
        modal.onkeydown = null;
        resolve(val);
      };
      ok.onclick = () => done(true);
      $("#modal-cancel").onclick = () => done(false);
      modal.onkeydown = (e) => { if (e.key === "Escape") done(false); };
    });
  }

  function notice(kind, html) { return `<div class="notice ${kind}" role="note">${html}</div>`; }
  function kpi(label, value, cls = "") { return `<div class="card kpi ${cls}"><div class="value">${esc(value)}</div><div class="label">${esc(label)}</div></div>`; }
  function empty(msg) { return `<p class="muted">${esc(msg)}</p>`; }

  // ------------------------------------------------------------ shell
  function buildNav() {
    const nav = $("#sidebar");
    nav.innerHTML = PAGES.map((g) => {
      const items = g.items.filter(([, , role]) => can(role));
      if (!items.length) return "";
      return `<div class="group-label">${esc(g.group)}</div>` +
        items.map(([id, label]) => `<a href="#/${id}" data-page="${id}">${esc(label)}</a>`).join("");
    }).join("");
  }

  function showLogin(msg) {
    $("#app-view").hidden = true;
    $("#login-view").hidden = false;
    $("#login-error").textContent = msg || "";
    $("#login-form [name=username]").focus();
  }

  function showApp() {
    $("#login-view").hidden = true;
    $("#app-view").hidden = false;
    $("#user-badge").textContent = `${state.user.username} · ${state.user.role}`;
    buildNav();
  }

  async function boot() {
    try {
      state.user = await api("GET", "/api/auth/me");
      state.meta = await api("GET", "/api/meta");
      state.today = (await api("GET", "/api/dashboard")).today_npt;
      showApp();
      route();
    } catch (e) {
      if (e.message !== "401") showLogin("");
    }
  }

  // ------------------------------------------------------------ router
  const pages = {
    overview: renderOverview, sources: renderSources, groups: renderGroups, facebook: renderFacebook,
    reports: renderReports, classes: renderClasses, educators: renderEducators, parents: renderParents,
    alerts: renderAlerts, archive: renderArchive, email: renderEmail, scheduler: renderScheduler,
    privacy: renderPrivacy, users: renderUsers, system: renderSystem,
  };

  async function route() {
    if (!state.user) return;
    const id = (location.hash.replace(/^#\//, "") || "overview").split("?")[0];
    const page = PAGES.flatMap((g) => g.items).find(([pid]) => pid === id);
    const target = page && can(page[2]) ? id : "overview";
    document.querySelectorAll(".sidebar a").forEach((a) => {
      a.toggleAttribute("aria-current", a.dataset.page === target);
      if (a.dataset.page === target) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
    $("#sidebar").classList.remove("open");
    $("#nav-toggle").setAttribute("aria-expanded", "false");
    content().innerHTML = '<p class="muted">Loading…</p>';
    try {
      await pages[target]();
    } catch (e) {
      if (e.message !== "401") content().innerHTML = notice("bad", `Could not load this page: ${esc(e.message)}`);
    }
    content().focus({ preventScroll: true });
  }

  // ------------------------------------------------------------ overview
  async function renderOverview() {
    const d = await api("GET", "/api/dashboard");
    const src = await api("GET", "/api/sources");
    const fb = src.facebook;
    const warnings = [];
    if (!d.email_configured) warnings.push(notice("warn", "<b>Email delivery is not configured.</b> Reports will be generated and archived, but <b>not</b> delivered to kptcc@gmail.com until SMTP is set in the environment."));
    if (d.demo_data) warnings.unshift(notice("bad", "<b>DEMO DATABASE — synthetic test conversations only.</b> Nothing shown here is real school data. Do not use this database for live reporting."));
    if (!fb.connected) warnings.push(notice("info", `<b>Facebook Page API is not connected.</b> ${esc(fb.detail)} Manual post import remains available.`));
    if (src.groups_configured === 0) warnings.push(notice("warn", "No WhatsApp groups are registered yet. Add the approved class-wise and educator groups in the registry."));
    else if (src.groups_synced_today < src.groups_configured) warnings.push(notice("warn", `Only <b>${esc(src.groups_synced_today)}</b> of <b>${esc(src.groups_configured)}</b> registered groups have data for today. The others are shown as <i>no data</i>, not as zero activity.`));
    if (d.failed_connections_recent) warnings.push(notice("bad", `${esc(d.failed_connections_recent)} recent failed import/sync event(s). See System health.`));
    content().innerHTML = `
      <div class="page-head"><h2>Dashboard overview</h2>
        <div class="btn-row">
          ${can("leadership") ? '<button class="btn primary" id="gen-btn">Generate Today\'s Report</button>' : ""}
          ${can("admin") ? '<button class="btn" id="test-btn">Send Test Email</button>' : ""}
        </div></div>
      <p class="muted">Reporting day (Asia/Kathmandu): <b>${esc(d.today_npt)}</b> · Next scheduled report: <b>${esc(d.next_report_at || "not scheduled")}</b></p>
      ${warnings.join("")}
      <div class="grid">
        ${kpi("Configured WhatsApp groups", d.whatsapp_groups_configured)}
        ${kpi("Groups with data today", d.whatsapp_groups_synced_today, d.whatsapp_groups_synced_today ? "ok" : "warn")}
        ${kpi("Facebook Page", fb.connected ? "Connected" : (fb.configured ? "Not verified" : "Not configured"), fb.connected ? "ok" : "warn")}
        ${kpi("Messages processed today", d.messages_today)}
        ${kpi("High-priority items today", d.high_priority_today, d.high_priority_today ? "alert" : "")}
        ${kpi("Open action items", d.open_actions, d.open_actions ? "warn" : "")}
        ${kpi("Failed connections (recent)", d.failed_connections_recent, d.failed_connections_recent ? "alert" : "ok")}
        ${kpi("Email delivery", d.email_configured ? "Configured" : "Not configured", d.email_configured ? "ok" : "warn")}
      </div>
      <div class="two-col">
        <section class="section" aria-labelledby="lr"><h3 id="lr">Latest report</h3>
          ${d.latest_report ? `<p>Date <b>${esc(d.latest_report.date)}</b> · status ${statusChip(d.latest_report.status, d.latest_report.status === "sent" ? "ok" : d.latest_report.status === "failed" ? "bad" : "info")} · engine ${esc(d.latest_report.engine)}</p>
            <p><a href="#/reports">Open report archive →</a></p>` : empty("No report has been generated yet.")}
          <p class="fine">Last successful data collection: ${fmtDate(d.last_successful_collection)}</p>
        </section>
        <section class="section" aria-labelledby="sc"><h3 id="sc">Coverage status</h3>
          <div class="status-line">${statusChip(`WhatsApp: ${src.groups_synced_today}/${src.groups_configured} groups`, src.groups_synced_today ? "ok" : "warn")}
          ${statusChip(`Facebook: ${fb.connected ? "API connected" : "not connected"}`, fb.connected ? "ok" : "warn")}
          ${statusChip(`Email: ${d.email_configured ? "configured" : "not configured"}`, d.email_configured ? "ok" : "warn")}</div>
          <p class="fine">Live WhatsApp API: not connected (by design — data arrives via authorized exports).</p>
        </section>
      </div>`;
    const g = $("#gen-btn");
    if (g) g.onclick = generateToday;
    const t = $("#test-btn");
    if (t) t.onclick = sendTest;
  }

  async function generateToday() {
    const ok = await confirmDialog("Generate today's report?",
      `<p>This runs the analysis for <b>${esc(state.today)}</b> and <b>sends it by email</b> to the configured recipient if SMTP is configured.</p>
       <p class="fine">Use the report archive to regenerate without sending.</p>`, "Generate and send");
    if (!ok) return;
    try {
      const r = await api("POST", "/api/reports/generate", { confirm: true, send: true });
      toast(`Report ${r.report_date} generated. Email: ${r.send_status}.`, 6000);
      route();
    } catch (e) { toast("Generation failed: " + e.message, 6000); }
  }

  async function sendTest() {
    const ok = await confirmDialog("Send a test email?",
      `<p>A test message with <b>no school data</b> will be sent to <b>${esc(state.meta ? "the configured recipient" : "")}</b>.</p>`, "Send test");
    if (!ok) return;
    try {
      const r = await api("POST", "/api/email/test", { confirm: true });
      toast(r.status === "accepted" ? `Test email accepted by provider (${r.attempts} attempt(s)).` : `Test email: ${r.status} — ${r.detail}`, 7000);
    } catch (e) { toast("Test email failed: " + e.message, 6000); }
  }

  // ------------------------------------------------------------ sources
  async function renderSources() {
    const s = await api("GET", "/api/sources");
    const fb = s.facebook;
    const rows = s.groups.map((g) => {
      const st = { data_received_today: ["ok", "Data received today"], no_data_today: ["warn", "No data today"],
        never_imported: ["bad", "Never imported"], inactive: ["neutral", "Inactive"], archived: ["neutral", "Archived"] }[g.import_status] || ["neutral", g.import_status];
      return `<tr><td>${esc(g.name)}</td><td>${esc(g.category)}</td><td>${esc(g.class_level || "—")}</td>
        <td>${esc(g.collection_method)}</td><td>${fmtDate(g.last_sync_at)}</td><td>${fmtDate(g.last_message_at)}</td>
        <td>${esc(g.messages_today)}</td><td>${statusChip(st[1], st[0])}</td></tr>`;
    }).join("");
    const groupOpts = s.groups.filter((g) => g.active && !g.archived)
      .map((g) => `<option value="${esc(g.id)}">${esc(g.name)}</option>`).join("");
    content().innerHTML = `
      <div class="page-head"><h2>Source connections</h2></div>
      <div class="grid">
        ${kpi("WhatsApp groups configured", s.groups_configured)}
        ${kpi("Synced today", s.groups_synced_today, s.groups_synced_today ? "ok" : "warn")}
        ${kpi("Facebook Page", fb.connected ? "Connected" : "Not connected", fb.connected ? "ok" : "warn")}
        ${kpi("Recent failures", s.failed_recent.length, s.failed_recent.length ? "alert" : "ok")}
      </div>
      <div class="two-col">
        <section class="section" aria-labelledby="wa"><h3 id="wa">WhatsApp</h3>
          ${notice("info", "<b>Live WhatsApp connection: not connected.</b> " + esc(s.whatsapp.mode))}
          <p class="fine">Last successful collection: ${fmtDate(s.last_successful_collection)}</p>
          ${can("staff") ? `<h3>Upload an authorized chat export</h3>
          <form id="upload-form" class="stack">
            <label>Registered group <select name="group_id" required><option value="">Choose a group…</option>${groupOpts}</select></label>
            <label>Export file (.txt, max 5 MB) <input type="file" name="file" accept=".txt,text/plain" required></label>
            <button class="btn primary" type="submit">Import export</button>
          </form>
          <p class="fine">Export from WhatsApp: group → ⋮ → More → Export chat → Without media.</p>` : ""}
          ${can("admin") ? `<div class="btn-row"><button class="btn" id="watch-btn">Scan watch folder now</button></div>` : ""}
          <div id="import-result"></div>
        </section>
        <section class="section" aria-labelledby="fbs"><h3 id="fbs">Facebook Page</h3>
          ${fb.connected ? notice("ok", `<b>Connected:</b> ${esc(fb.page_name)}`) : notice("warn", `<b>Not connected.</b> ${esc(fb.detail)}`)}
          <p>Page URL: ${fb.page_url ? `<a href="${esc(fb.page_url)}" rel="noopener noreferrer" target="_blank">${esc(fb.page_url)}</a>` : '<span class="muted">not configured</span>'}
          ${fb.page_url && !fb.page_url_verified ? ' <span class="chip warn">unverified</span>' : ""}</p>
          <p class="fine">Last API sync: ${fmtDate(fb.last_sync_at)}</p>
          ${fb.last_error ? notice("bad", "Last error: " + esc(fb.last_error)) : ""}
        </section>
      </div>
      <section class="section" aria-labelledby="gt"><h3 id="gt">Registered sources and today's status</h3>
        <div class="table-wrap"><table><caption class="sr-only">Source status</caption>
        <thead><tr><th scope="col">Group</th><th scope="col">Category</th><th scope="col">Class</th><th scope="col">Method</th><th scope="col">Last sync</th><th scope="col">Last message</th><th scope="col">Today</th><th scope="col">Status</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="8">No groups registered. Add them in the WhatsApp group registry.</td></tr>'}</tbody></table></div>
      </section>
      ${s.failed_recent.length ? `<section class="section"><h3>Recent failures</h3><ul class="clean">${s.failed_recent.map((f) => `<li>${esc(f.at)} — <b>${esc(f.source)}</b>: ${esc(f.error)}</li>`).join("")}</ul></section>` : ""}`;

    const up = $("#upload-form");
    if (up) up.onsubmit = async (e) => {
      e.preventDefault();
      const fd = new FormData(up);
      const out = $("#import-result");
      out.innerHTML = '<p class="muted">Importing…</p>';
      try {
        const r = await api("POST", "/api/imports/whatsapp", fd, { form: true });
        out.innerHTML = notice(r.status === "success" ? "ok" : "warn",
          `<b>${esc(r.file)}</b> → ${esc(r.group)}: ${esc(r.new)} new, ${esc(r.duplicate)} duplicate(s) skipped, ${esc(r.malformed)} malformed line(s). Timestamps preserved (NPT).`);
        up.reset();
      } catch (err) { out.innerHTML = notice("bad", "Import failed: " + esc(err.message)); }
    };
    const w = $("#watch-btn");
    if (w) w.onclick = async () => {
      try { const r = await api("POST", "/api/scheduler/watch-now", { confirm: true }); toast(`Watch folder scanned: ${r.results.length} file(s).`); route(); }
      catch (e) { toast("Scan failed: " + e.message); }
    };
  }

  // ------------------------------------------------------------ group registry
  async function renderGroups() {
    const groups = await api("GET", "/api/groups?include_archived=true");
    const cats = state.meta.categories.map((c) => `<option>${esc(c)}</option>`).join("");
    const classes = state.meta.classes.map((c) => `<option>${esc(c)}</option>`).join("");
    const rows = groups.map((g) => `<tr>
      <td>${esc(g.name)}</td><td>${esc(g.category)}</td><td>${esc(g.class_level || "—")}</td><td>${esc(g.academic_year || "—")}</td>
      <td>${esc(g.group_admin || "—")}</td><td>${esc(g.collection_method)}</td><td>${fmtDate(g.last_sync_at)}</td>
      <td>${fmtDate(g.last_message_at)}</td>
      <td>${g.archived ? statusChip("Archived", "neutral") : g.is_active ? statusChip("Active", "ok") : statusChip("Inactive", "warn")}</td>
      <td>${can("leadership") ? `<label class="inline-check"><input type="checkbox" data-include="${esc(g.id)}" ${g.include_in_reporting ? "checked" : ""} ${g.archived ? "disabled" : ""}> <span class="sr-only">Include ${esc(g.name)} in report</span>${g.include_in_reporting ? "Included" : "Excluded"}</label>` : (g.include_in_reporting ? "Included" : "Excluded")}</td>
      <td>${can("leadership") && !g.archived ? `<div class="btn-row"><button class="btn" data-edit="${esc(g.id)}">Edit</button>
        <button class="btn" data-toggle-active="${esc(g.id)}">${g.is_active ? "Deactivate" : "Activate"}</button>
        <button class="btn danger" data-archive="${esc(g.id)}">Archive</button></div>` : ""}</td></tr>`).join("");
    content().innerHTML = `
      <div class="page-head"><h2>WhatsApp group registry</h2>
        ${can("leadership") ? '<button class="btn primary" id="add-group">Add group</button>' : ""}</div>
      ${notice("info", "Register only groups for which the school has authorization. Inclusion in reporting is controlled per group; archived groups keep their history.")}
      <div class="table-wrap"><table><caption class="sr-only">WhatsApp groups</caption>
      <thead><tr><th scope="col">Name</th><th scope="col">Category</th><th scope="col">Class</th><th scope="col">Year</th><th scope="col">Admin</th><th scope="col">Method</th><th scope="col">Last sync</th><th scope="col">Last message</th><th scope="col">State</th><th scope="col">Report</th><th scope="col">Actions</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="11">No groups yet.</td></tr>'}</tbody></table></div>`;

    const openForm = (g) => {
      const v = g || { name: "", category: "Class Group", class_level: "", academic_year: "", group_admin: "", collection_method: "export_upload", include_in_reporting: true, authorization_noted: false };
      const html = `<form id="grp-form" class="stack">
        <label>Group name <input name="name" required minlength="2" maxlength="200" value="${esc(v.name)}"></label>
        <label>Category <select name="category">${state.meta.categories.map((c) => `<option ${c === v.category ? "selected" : ""}>${esc(c)}</option>`).join("")}</select></label>
        <label>Class <select name="class_level"><option value="">— none —</option>${state.meta.classes.map((c) => `<option ${c === v.class_level ? "selected" : ""}>${esc(c)}</option>`).join("")}</select></label>
        <label>Academic year <input name="academic_year" maxlength="20" value="${esc(v.academic_year)}" placeholder="e.g. 2083"></label>
        <label>Group administrator (role, not personal number) <input name="group_admin" maxlength="120" value="${esc(v.group_admin)}"></label>
        <label>Authorized collection method <select name="collection_method">
          ${["export_upload", "watch_folder", "manual"].map((m) => `<option value="${m}" ${m === v.collection_method ? "selected" : ""}>${m.replace("_", " ")}</option>`).join("")}</select></label>
        <label class="inline-check"><input type="checkbox" name="include_in_reporting" ${v.include_in_reporting ? "checked" : ""}> Include in daily report</label>
        <label class="inline-check"><input type="checkbox" name="authorization_noted" ${v.authorization_noted ? "checked" : ""}> Written authorization and member notice on file</label>
      </form>`;
      confirmDialog(g ? "Edit group" : "Add group", html, "Save").then(async (ok) => {
        if (!ok) return;
        const f = $("#grp-form");
        if (!f.reportValidity()) return;
        const fd = new FormData(f);
        const body = {
          name: fd.get("name"), category: fd.get("category"), class_level: fd.get("class_level") || "",
          academic_year: fd.get("academic_year") || "", group_admin: fd.get("group_admin") || "",
          collection_method: fd.get("collection_method"), include_in_reporting: f.include_in_reporting.checked,
          authorization_noted: f.authorization_noted.checked,
        };
        try {
          if (g) await api("PATCH", `/api/groups/${g.id}`, body); else await api("POST", "/api/groups", body);
          toast("Group saved.");
          route();
        } catch (e) { toast("Save failed: " + e.message, 6000); }
      });
    };
    const add = $("#add-group"); if (add) add.onclick = () => openForm(null);
    content().querySelectorAll("[data-edit]").forEach((b) => b.onclick = () => openForm(groups.find((g) => String(g.id) === b.dataset.edit)));
    content().querySelectorAll("[data-toggle-active]").forEach((b) => b.onclick = async () => {
      const g = groups.find((x) => String(x.id) === b.dataset.toggleActive);
      await api("PATCH", `/api/groups/${g.id}`, { is_active: !g.is_active, include_in_reporting: g.is_active ? false : g.include_in_reporting });
      toast(g.is_active ? "Group deactivated." : "Group activated."); route();
    });
    content().querySelectorAll("[data-archive]").forEach((b) => b.onclick = async () => {
      const g = groups.find((x) => String(x.id) === b.dataset.archive);
      const ok = await confirmDialog("Archive group?", `<p><b>${esc(g.name)}</b> will be excluded from future reports. Existing history is kept.</p>`, "Archive", true);
      if (!ok) return;
      await api("PATCH", `/api/groups/${g.id}`, { archived: true }); toast("Group archived."); route();
    });
    content().querySelectorAll("[data-include]").forEach((c) => c.onchange = async () => {
      try { await api("PATCH", `/api/groups/${c.dataset.include}`, { include_in_reporting: c.checked }); toast("Reporting inclusion updated."); }
      catch (e) { c.checked = !c.checked; toast(e.message); }
      route();
    });
  }

  // ------------------------------------------------------------ facebook
  async function renderFacebook() {
    const s = await api("GET", "/api/sources");
    const fb = s.facebook;
    content().innerHTML = `
      <div class="page-head"><h2>Facebook Page integration</h2>
        ${can("admin") ? '<button class="btn" id="fb-sync">Sync from Meta API now</button>' : ""}</div>
      ${fb.connected ? notice("ok", `<b>Connected via Meta Graph API:</b> ${esc(fb.page_name)}`) :
        notice("warn", `<b>Not connected.</b> ${esc(fb.detail)} See docs/META_FACEBOOK_SETUP.md. Until then, no Facebook data is claimed as collected.`)}
      <div class="two-col">
        <section class="section" aria-labelledby="fbm"><h3 id="fbm">Manual post import (fallback)</h3>
          ${can("staff") ? `<form id="fb-manual" class="stack">
            <label>Post text (copy from the Page) <textarea name="text" required minlength="3" maxlength="8000"></textarea></label>
            <label>Public post URL (https only, optional) <input name="url" type="url" maxlength="400" placeholder="https://www.facebook.com/…"></label>
            <label>Published date/time (optional, YYYY-MM-DDTHH:MM) <input name="published_at" type="datetime-local"></label>
            <div class="filters"><label>Reactions (if shown) <input name="reactions" type="number" min="0"></label>
            <label>Comments (if shown) <input name="comments_count" type="number" min="0"></label></div>
            <button class="btn primary" type="submit">Save post</button>
          </form><p class="fine">Figures entered here are staff-provided and are labelled as manual in reports.</p>` : empty("Your role cannot import posts.")}
        </section>
        <section class="section" aria-labelledby="fbp"><h3 id="fbp">What the connected API provides</h3>
          <ul class="clean"><li>Page posts within the reporting window, with timestamps and permalinks.</li>
          <li>Comments and reaction totals <b>only where Meta returns them</b>; missing values are shown as n/a.</li>
          <li>Reach, impressions and follower growth are <b>not</b> estimated and not shown unless Meta provides them.</li>
          <li>No private profiles, Messenger threads or closed groups are accessed.</li></ul>
          <p class="fine">Last API sync: ${fmtDate(fb.last_sync_at)}</p>
        </section>
      </div>`;
    const f = $("#fb-manual");
    if (f) f.onsubmit = async (e) => {
      e.preventDefault();
      const fd = new FormData(f);
      const body = { text: fd.get("text"), url: fd.get("url") || "" };
      if (fd.get("published_at")) body.published_at = new Date(fd.get("published_at")).toISOString();
      if (fd.get("reactions") !== "") body.reactions = Number(fd.get("reactions"));
      if (fd.get("comments_count") !== "") body.comments_count = Number(fd.get("comments_count"));
      try { await api("POST", "/api/facebook/manual-post", body); toast("Post saved to the archive."); f.reset(); }
      catch (err) { toast("Not saved: " + err.message, 6000); }
    };
    const sy = $("#fb-sync");
    if (sy) sy.onclick = async () => {
      try { const r = await api("POST", "/api/facebook/sync"); toast(r.ok ? `Synced ${r.posts_fetched} post(s).` : "Sync failed: " + r.error, 6000); route(); }
      catch (e) { toast("Sync failed: " + e.message, 6000); }
    };
  }

  // ------------------------------------------------------------ reports
  async function loadReportForDate(day) {
    try { return await api("GET", `/api/reports/by-date/${encodeURIComponent(day)}`); }
    catch (e) { return null; }
  }

  function dateToolbar(current, path) {
    return `<form class="filters" id="date-form" aria-label="Choose report date">
      <label>Report date (YYYY-MM-DD) <input type="date" name="day" value="${esc(current)}" required></label>
      <div><button class="btn" type="submit">Show</button></div></form>`;
  }

  async function renderReports() {
    const reports = await api("GET", "/api/reports");
    const hash = location.hash.split("?")[1] || "";
    const params = new URLSearchParams(hash);
    const day = params.get("date") || (reports[0] ? reports[0].report_date : state.today);
    const rep = await loadReportForDate(day);
    const list = reports.length ? `<div class="table-wrap"><table><caption>Report archive</caption>
      <thead><tr><th scope="col">Date</th><th scope="col">Status</th><th scope="col">Engine</th><th scope="col">Coverage</th><th scope="col">Open</th></tr></thead><tbody>
      ${reports.map((r) => `<tr><td>${esc(r.report_date)}</td><td>${statusChip(r.status, r.status === "sent" ? "ok" : r.status === "failed" || r.status === "no_email_config" ? "bad" : "info")}</td>
        <td>${esc(r.engine)}</td><td>${esc(r.coverage.groups_with_data)}/${esc(r.coverage.groups_total)} groups</td>
        <td><a href="#/reports?date=${esc(r.report_date)}">View</a></td></tr>`).join("")}</tbody></table></div>` : empty("No reports yet. Generate today's report from the overview.");
    let detail = empty("No report exists for this date.");
    if (rep) detail = renderReportDetail(rep);
    content().innerHTML = `
      <div class="page-head"><h2>Daily reports</h2>
        <div class="btn-row">
          ${rep && can("leadership") ? `<a class="btn" href="/api/reports/${esc(rep.id)}/html" target="_blank" rel="noopener">Open HTML email view</a>` : ""}
          ${rep && rep.pdf_available && can("leadership") ? `<a class="btn" href="/api/reports/${esc(rep.id)}/pdf">Download PDF</a>` : ""}
          ${rep && can("admin") ? `<button class="btn" id="resend-btn" data-id="${esc(rep.id)}">Resend by email</button>` : ""}
        </div></div>
      ${dateToolbar(day)}
      ${list}
      <div id="report-detail">${detail}</div>`;
    $("#date-form").onsubmit = (e) => { e.preventDefault(); location.hash = "#/reports?date=" + encodeURIComponent(new FormData(e.target).get("day")); };
    const rs = $("#resend-btn");
    if (rs) rs.onclick = async () => {
      const ok = await confirmDialog("Resend this report?", "<p>The report will be sent again to the configured recipient. This action is audited.</p>", "Resend");
      if (!ok) return;
      try { const r = await api("POST", `/api/reports/${rs.dataset.id}/resend`, { confirm: true }); toast(`Resend: ${r.status}. ${r.detail}`, 6000); route(); }
      catch (e) { toast("Resend failed: " + e.message, 6000); }
    };
  }

  function renderReportDetail(rep) {
    const d = rep.data || {};
    const cov = d.coverage || {};
    const alerts = (d.alerts || []).map((a) => `<div class="card ${a.priority === "CRITICAL" ? "alert" : "warn"}" style="margin-bottom:.6rem">
      <div>${chip(a.priority)} <b>${esc(a.issue)}</b></div>
      <p class="evidence"><b>Why:</b> ${esc(a.reason)}</p>
      <p class="evidence"><b>Sources (${esc(a.cross_source_count)}):</b> ${(a.sources || []).map((s) => `${esc(s.source)}${s.ts ? " @ " + esc(s.ts) : ""}`).join("; ")}</p>
      <div class="quote">${esc((a.sources && a.sources[0] && a.sources[0].excerpt) || "")}</div>
      <p class="evidence"><b>Status:</b> ${esc(a.status)} · <b>Next step:</b> ${esc(a.next_step)}</p></div>`).join("")
      || notice("ok", "No critical or high-priority issue was identified in the available data.");
    const bullets = (d.executive_bullets || []).map((b) => `<li>${esc(b)}</li>`).join("");
    const actions = (d.actions || []).map((a) => `<tr><td>${chip(a.priority)}</td><td><b>${esc(a.title)}</b><br><span class="evidence">${esc(a.detail)}</span></td>
      <td>${esc(a.role)}</td><td>${esc(a.deadline)}</td></tr>`).join("");
    const deadlines = (d.deadlines || []).map((x) => `<tr><td>${esc(x.date)}</td><td>${esc(x.what)}</td><td>${esc(x.source)} (${esc(x.platform)})</td></tr>`).join("");
    const limits = (d.limitations || []).map((l) => `<li>${esc(l)}</li>`).join("");
    return `<section class="section" aria-labelledby="rd-title">
      <h2 id="rd-title">${esc(rep.report_date)} · ${esc("KASHYAP VIDYAPEETH INARUWA")}</h2>
      <p class="muted">Generated ${esc(rep.generated_at || "")} · Report ID <code>${esc(rep.report_uid)}</code> · Engine ${esc(rep.engine)} · Status ${statusChip(rep.status, rep.status === "sent" ? "ok" : "info")}</p>
      ${rep.nepali_date ? `<p lang="ne">${esc(rep.nepali_date)}</p>` : ""}
      ${d.no_data ? notice("warn", "<b>DATA UNAVAILABLE</b> — no source data was received for this day. This is not a normal daily summary.") : ""}
      <h3>A. Principal's executive briefing</h3><ul class="clean">${bullets}</ul>
      ${d.nepali_summary ? `<div lang="ne" class="quote">${esc(d.nepali_summary)}</div>` : ""}
      <h3>B. Critical &amp; high-priority alerts</h3>${alerts}
      <h3>C. Class-wise summary</h3>
      <div class="table-wrap"><table><caption class="sr-only">Class-wise summary</caption><thead><tr><th scope="col">Class</th><th scope="col">Academic updates</th><th scope="col">Parent concerns</th><th scope="col">Pending actions</th><th scope="col">Priority</th></tr></thead><tbody>
      ${(d.class_rows || []).map((r) => {
        const unavailable = r.data_status === "no_data";
        const na_ = r.data_status === "not_configured";
        return `<tr><td>${esc(r.class)}</td>
          <td>${unavailable ? '<span class="chip warn">data unavailable (not zero)</span>' : na_ ? '<span class="muted">no group configured</span>' : `${esc(r.messages)} msg · HW ${esc((r.homework || []).length)} · exams ${esc((r.exams || []).length)}`}</td>
          <td>${unavailable || na_ ? "—" : `${esc((r.parent_concerns || []).length)} concern(s), ${esc((r.unanswered || []).length)} unanswered`}</td>
          <td>${esc((r.pending_actions || []).join("; ") || "—")}</td>
          <td>${chip(r.priority)}</td></tr>`; }).join("")}
      </tbody></table></div>
      <h3>G. Upcoming deadlines</h3>
      ${deadlines ? `<div class="table-wrap"><table><thead><tr><th scope="col">Date</th><th scope="col">Item</th><th scope="col">Source</th></tr></thead><tbody>${deadlines}</tbody></table></div>` : empty("No explicitly dated upcoming items in the available data.")}
      <h3>H. Principal's action plan</h3>
      ${actions ? `<div class="table-wrap"><table><thead><tr><th scope="col">Priority</th><th scope="col">Action</th><th scope="col">Suggested role</th><th scope="col">Deadline</th></tr></thead><tbody>${actions}</tbody></table></div>` : empty("No action items.")}
      <h3>J. Source coverage &amp; limitations</h3>
      <p>Coverage: <b>${esc(cov.groups_with_data)}</b> of <b>${esc(cov.groups_total)}</b> groups with data · Facebook ${cov.facebook && cov.facebook.connected ? "connected" : "not connected"}</p>
      <ul class="clean">${limits}</ul>
      <h3>K. Tomorrow's focus</h3><ol class="clean">${(d.tomorrow_focus || []).map((f) => `<li>${esc(f)}</li>`).join("")}</ol>
    </section>`;
  }

  async function renderClasses() {
    const day = (location.hash.split("?")[1] || "").replace(/^date=/, "") || state.today;
    const rep = await loadReportForDate(day);
    content().innerHTML = `<div class="page-head"><h2>Class-wise insights</h2></div>${dateToolbar(day)}
      ${!rep ? empty("No report for this date. Generate it from the overview or the reports page.") : `
      <div class="table-wrap"><table><caption>Class-wise academic communication, ${esc(day)}</caption>
      <thead><tr><th scope="col">Class</th><th scope="col">Messages</th><th scope="col">Homework / assignments</th><th scope="col">Assessments</th><th scope="col">Unanswered parent questions</th><th scope="col">Pending actions</th><th scope="col">Priority</th></tr></thead><tbody>
      ${(rep.data.class_rows || []).map((r) => `<tr><td><b>${esc(r.class)}</b></td>
        <td>${r.data_status === "no_data" ? '<span class="chip warn">no data</span>' : r.data_status === "not_configured" ? '<span class="muted">not configured</span>' : esc(r.messages)}</td>
        <td>${(r.homework || []).map((h) => `<div class="quote">${esc(h)}</div>`).join("") || "—"}</td>
        <td>${(r.exams || []).map((h) => `<div class="quote">${esc(h)}</div>`).join("") || "—"}</td>
        <td>${(r.unanswered || []).map((u) => `<div class="quote">${esc(u.excerpt)} <span class="evidence">${esc(u.source)}, ${esc(u.ts)}</span></div>`).join("") || "—"}</td>
        <td>${esc((r.pending_actions || []).join("; ") || "—")}</td><td>${chip(r.priority)}</td></tr>`).join("")}
      </tbody></table></div>
      <p class="fine">Message volume is not a measure of teaching quality. “No data” means no export was received, not zero activity.</p>`}`;
    const f = $("#date-form"); if (f) f.onsubmit = (e) => { e.preventDefault(); location.hash = "#/classes?date=" + new FormData(e.target).get("day"); };
  }

  async function renderEducators() {
    const day = (location.hash.split("?")[1] || "").replace(/^date=/, "") || state.today;
    const rep = await loadReportForDate(day);
    if (!rep) { content().innerHTML = `<div class="page-head"><h2>Educator coordination</h2></div>${dateToolbar(day)}${empty("No report for this date.")}`; bindDate("educators"); return; }
    const e = rep.data.educator || {};
    const list = (arr) => (arr && arr.length ? `<ul class="clean">${arr.map((x) => `<li><span class="quote">${esc(x.excerpt)}</span><span class="evidence">${esc(x.source)}${x.ts ? ", " + esc(x.ts) : ""}</span></li>`).join("")}</ul>` : empty("None recorded in the available data."));
    const status = Object.entries(e.activity_status_breakdown || {}).map(([k, v]) => `${esc(k)}: ${esc(v)}`).join(" · ") || "none";
    content().innerHTML = `<div class="page-head"><h2>Educator coordination</h2></div>${dateToolbar(day)}
      ${notice("info", esc(e.note || ""))}
      <p>${esc(e.messages || 0)} educator message(s) across ${esc((e.groups_active || []).length)} group(s). Activity status (as communicated): ${esc(status)}</p>
      <div class="two-col">
        <section class="section"><h3>Planning &amp; resources shared</h3>${list(e.planning_resources)}</section>
        <section class="section"><h3>Meetings &amp; instructions</h3>${list(e.meetings_coordination)}</section>
        <section class="section"><h3>Assessment updates</h3>${list(e.assessment_updates)}</section>
        <section class="section"><h3>Support requested</h3>${list(e.support_requested)}</section>
      </div>`;
    bindDate("educators");
  }

  async function renderParents() {
    const day = (location.hash.split("?")[1] || "").replace(/^date=/, "") || state.today;
    const rep = await loadReportForDate(day);
    if (!rep) { content().innerHTML = `<div class="page-head"><h2>Parent concerns</h2></div>${dateToolbar(day)}${empty("No report for this date.")}`; bindDate("parents"); return; }
    const p = rep.data.parent || {};
    content().innerHTML = `<div class="page-head"><h2>Parent concerns</h2></div>${dateToolbar(day)}
      <div class="grid">${kpi("Questions", p.questions_total || 0)}${kpi("Answered", p.answered || 0, "ok")}${kpi("Unanswered", p.unanswered_count || 0, p.unanswered_count ? "warn" : "ok")}${kpi("Concerns", (p.concerns || []).length)}</div>
      <div class="two-col">
        <section class="section"><h3>Awaiting response</h3>${(p.unanswered || []).map((u) => `<div class="quote">${esc(u.excerpt)}<br><span class="evidence">${esc(u.source)}, ${esc(u.ts)} · ${esc(u.status)}</span></div>`).join("") || empty("No unanswered questions in the imported data.")}</section>
        <section class="section"><h3>Grouped questions</h3>${(p.question_clusters || []).map((q) => `<div class="quote">${esc(q.question)} <span class="evidence">×${esc(q.occurrences)} — ${esc((q.sources || []).join(", "))}</span></div>`).join("") || empty("None.")}</section>
        <section class="section"><h3>Concerns raised</h3>${(p.concerns || []).map((c) => `<div class="quote">${esc(c.excerpt)} <span class="evidence">${esc(c.source)}</span></div>`).join("") || empty("None recorded.")}</section>
        <section class="section"><h3>Positive feedback</h3>${(p.positive_feedback || []).map((c) => `<div class="quote">${esc(c.excerpt)} <span class="evidence">${esc(c.source)}</span></div>`).join("") || empty("None recorded.")}</section>
      </div>
      <p class="fine">${esc(p.tone_note || "")}</p>`;
    bindDate("parents");
  }

  function bindDate(page) {
    const f = $("#date-form"); if (f) f.onsubmit = (e) => { e.preventDefault(); location.hash = `#/${page}?date=` + new FormData(e.target).get("day"); };
  }

  // ------------------------------------------------------------ alerts & actions
  async function renderAlerts() {
    const q = new URLSearchParams(location.hash.split("?")[1] || "");
    const status = q.get("status") || ""; const priority = q.get("priority") || "";
    const actions = await api("GET", `/api/actions?${status ? "status=" + encodeURIComponent(status) + "&" : ""}${priority ? "priority=" + encodeURIComponent(priority) : ""}`);
    const rep = await loadReportForDate(state.today);
    const alerts = rep ? (rep.data.alerts || []) : [];
    const opts = (arr, cur) => arr.map((x) => `<option value="${esc(x)}" ${x === cur ? "selected" : ""}>${esc(x)}</option>`).join("");
    content().innerHTML = `<div class="page-head"><h2>Alerts &amp; action tracker</h2></div>
      <section class="section" aria-labelledby="al"><h3 id="al">Alerts for ${esc(state.today)}</h3>
        ${alerts.length ? alerts.map((a) => `<div class="card ${a.priority === "CRITICAL" ? "alert" : "warn"}" style="margin-bottom:.6rem"><div>${chip(a.priority)} <b>${esc(a.issue)}</b></div>
          <p class="evidence">${esc(a.reason)} · ${esc(a.status)}</p><p class="evidence">Next: ${esc(a.next_step)}</p></div>`).join("") : empty("No critical or high-priority alerts for today's report.")}
      </section>
      <form id="act-filter" class="filters" aria-label="Filter actions">
        <label>Status <select name="status"><option value="">All</option>${opts(["open", "in_progress", "resolved", "dismissed"], status)}</select></label>
        <label>Priority <select name="priority"><option value="">All</option>${opts(state.meta.priorities, priority)}</select></label>
        <div><button class="btn" type="submit">Apply</button></div></form>
      <div class="table-wrap"><table><caption>Action register</caption>
      <thead><tr><th scope="col">ID</th><th scope="col">Date</th><th scope="col">Action</th><th scope="col">Priority</th><th scope="col">Role</th><th scope="col">Deadline</th><th scope="col">Status</th><th scope="col">Update</th></tr></thead><tbody>
      ${actions.map((a) => `<tr><td>${esc(a.action_id)}</td><td>${esc(a.report_date)}</td><td><b>${esc(a.title)}</b><br><span class="evidence">${esc(a.detail)}</span></td>
        <td>${chip(a.priority)}</td><td>${esc(a.suggested_role)}</td><td>${esc(a.deadline)}</td><td>${statusChip(a.status, a.status === "resolved" ? "ok" : a.status === "open" ? "warn" : "info")}</td>
        <td>${can("leadership") ? `<div class="btn-row"><select aria-label="New status for ${esc(a.action_id)}" data-act="${esc(a.id)}">${opts(["open", "in_progress", "resolved", "dismissed"], a.status)}</select>
          <button class="btn" data-save="${esc(a.id)}">Save</button></div><textarea aria-label="Resolution notes" data-notes="${esc(a.id)}" placeholder="Resolution notes">${esc(a.resolution_notes)}</textarea>` : esc(a.resolution_notes)}</td></tr>`).join("") || '<tr><td colspan="8">No actions match these filters.</td></tr>'}
      </tbody></table></div>`;
    $("#act-filter").onsubmit = (e) => { e.preventDefault(); const f = new FormData(e.target); location.hash = `#/alerts?status=${encodeURIComponent(f.get("status"))}&priority=${encodeURIComponent(f.get("priority"))}`; };
    content().querySelectorAll("[data-save]").forEach((b) => b.onclick = async () => {
      const id = b.dataset.save;
      const st = content().querySelector(`[data-act="${id}"]`).value;
      const notes = content().querySelector(`[data-notes="${id}"]`).value;
      try { await api("PATCH", `/api/actions/${id}`, { status: st, resolution_notes: notes }); toast("Action updated."); }
      catch (e) { toast("Update failed: " + e.message); }
    });
  }

  // ------------------------------------------------------------ archive
  async function renderArchive() {
    const q = new URLSearchParams(location.hash.split("?")[1] || "");
    const qs = new URLSearchParams();
    ["q", "date_from", "date_to", "class_level", "priority", "category", "group_id"].forEach((k) => { if (q.get(k)) qs.set(k, q.get(k)); });
    const reveal = q.get("reveal") === "1" && can("leadership");
    if (reveal) qs.set("reveal", "true");
    const groups = await api("GET", "/api/groups");
    const data = await api("GET", "/api/archive?" + qs.toString());
    const classes = state.meta.classes.map((c) => `<option ${q.get("class_level") === c ? "selected" : ""}>${esc(c)}</option>`).join("");
    const cats = state.meta.categories.map((c) => `<option ${q.get("category") === c ? "selected" : ""}>${esc(c)}</option>`).join("");
    const gopts = groups.map((g) => `<option value="${esc(g.id)}" ${String(g.id) === q.get("group_id") ? "selected" : ""}>${esc(g.name)}</option>`).join("");
    const pr = state.meta.priorities.map((p) => `<option ${q.get("priority") === p ? "selected" : ""}>${esc(p)}</option>`).join("");
    content().innerHTML = `<div class="page-head"><h2>Searchable communication archive</h2>
      ${can("leadership") ? `<label class="inline-check"><input type="checkbox" id="reveal" ${reveal ? "checked" : ""}> Show original text (audited)</label>` : ""}</div>
      ${reveal ? notice("warn", "Original message text is visible. Use only for authorized follow-up. Access is logged.") : notice("info", "Showing redacted text (phone numbers, e-mail addresses and long ID numbers removed). Sender names are masked for your role.")}
      <form id="arch-form" class="filters" aria-label="Archive filters">
        <label>Search text <input name="q" value="${esc(q.get("q") || "")}" maxlength="200"></label>
        <label>From <input type="date" name="date_from" value="${esc(q.get("date_from") || "")}"></label>
        <label>To <input type="date" name="date_to" value="${esc(q.get("date_to") || "")}"></label>
        <label>Class <select name="class_level"><option value="">All</option>${classes}</select></label>
        <label>Source group <select name="group_id"><option value="">All</option>${gopts}</select></label>
        <label>Category <select name="category"><option value="">All</option>${cats}</select></label>
        <label>Priority <select name="priority"><option value="">All</option>${pr}</select></label>
        <div><button class="btn primary" type="submit">Search</button></div>
      </form>
      <p class="muted">${esc(data.total)} result(s). Showing ${esc(data.items.length)}.</p>
      <div class="table-wrap"><table><caption class="sr-only">Archive results</caption>
      <thead><tr><th scope="col">Time (NPT)</th><th scope="col">Source</th><th scope="col">Sender</th><th scope="col">Priority</th><th scope="col">Categories</th><th scope="col">Message</th></tr></thead><tbody>
      ${data.items.map((m) => `<tr><td>${esc(m.ts_original)}</td><td>${esc(m.group)}<br><span class="evidence">${esc(m.class_level || "")}</span></td>
        <td>${esc(m.sender)}<br><span class="evidence">${esc(m.sender_kind)}</span></td><td>${chip(m.priority)}<br><span class="evidence">${esc(m.priority_reason)}</span></td>
        <td>${(m.categories || []).map((c) => `<span class="chip info">${esc(c)}</span>`).join(" ")}${m.is_question ? `<br><span class="evidence">question${m.question_answered === true ? " · answered" : m.question_answered === false ? " · unanswered" : ""}</span>` : ""}</td>
        <td><div class="quote">${esc(m.text)}</div></td></tr>`).join("") || '<tr><td colspan="6">No messages match.</td></tr>'}
      </tbody></table></div>`;
    $("#arch-form").onsubmit = (e) => {
      e.preventDefault();
      const f = new FormData(e.target); const p = new URLSearchParams();
      for (const [k, v] of f.entries()) if (v) p.set(k, v);
      if (reveal) p.set("reveal", "1");
      location.hash = "#/archive?" + p.toString();
    };
    const rv = $("#reveal");
    if (rv) rv.onchange = () => {
      const p = new URLSearchParams(location.hash.split("?")[1] || "");
      if (rv.checked) {
        confirmDialog("Show original text?", "<p>Original messages may contain personal details. Only reveal for an authorized follow-up. This is recorded in the audit log.</p>", "Show original").then((ok) => {
          if (ok) { p.set("reveal", "1"); location.hash = "#/archive?" + p.toString(); } else rv.checked = false;
        });
      } else { p.delete("reveal"); location.hash = "#/archive?" + p.toString(); }
    };
  }

  // ------------------------------------------------------------ email logs
  async function renderEmail() {
    const logs = await api("GET", "/api/email/logs");
    const reports = await api("GET", "/api/reports");
    const kindLabel = { daily: "Daily report", test: "Test", resend: "Resend", failure_notice: "Failure notice", backup: "Backup copy" };
    const statusKind = { accepted: "ok", failed: "bad", skipped_duplicate: "info", not_configured: "warn", queued: "info" };
    content().innerHTML = `<div class="page-head"><h2>Email delivery logs</h2></div>
      <p class="muted">A report is marked <b>sent</b> only when the mail server accepts the message. Generation alone is not delivery.</p>
      <div class="table-wrap"><table><caption>Delivery attempts</caption>
      <thead><tr><th scope="col">Time (NPT)</th><th scope="col">Type</th><th scope="col">Report ID</th><th scope="col">Attempt</th><th scope="col">Recipient</th><th scope="col">Status</th><th scope="col">Provider response</th><th scope="col">PDF</th></tr></thead><tbody>
      ${logs.map((l) => `<tr><td>${esc(l.created_at.replace("T", " ").slice(0, 16))}</td><td>${esc(kindLabel[l.kind] || l.kind)}</td><td><code>${esc(l.report_uid ? l.report_uid.slice(0, 10) : "—")}</code></td>
        <td>${esc(l.attempt)}</td><td>${esc(l.to)}</td><td>${statusChip(l.status, statusKind[l.status] || "neutral")}</td><td class="evidence">${esc(l.provider_response)}</td><td>${l.has_pdf ? "yes" : "no"}</td></tr>`).join("") || '<tr><td colspan="8">No delivery attempts yet.</td></tr>'}
      </tbody></table></div>
      ${can("admin") && reports.length ? `<p class="fine">To resend a report, open it from the Daily reports page.</p>` : ""}`;
  }

  // ------------------------------------------------------------ scheduler
  async function renderScheduler() {
    const s = await api("GET", "/api/scheduler");
    content().innerHTML = `<div class="page-head"><h2>Scheduler settings</h2></div>
      <div class="grid">
        ${kpi("Daily report time", s.report_time + " " + s.timezone)}
        ${kpi("Scheduler running", s.running ? "Yes" : "No", s.running ? "ok" : "alert")}
        ${kpi("Watch-folder interval", s.watch_interval_min + " min")}
      </div>
      <section class="section"><h3>Next scheduled report</h3>
        <p><b>${esc(s.next_report_at_npt || "not scheduled")}</b></p>
        ${notice("info", "The report runs every day at the configured time in Asia/Kathmandu (including weekends). It is safe against double runs: a report already sent is never sent again automatically. Times are set in the environment file (KVI_REPORT_HOUR, KVI_REPORT_MINUTE, KVI_TIMEZONE) and apply after a restart.")}
        ${!s.running ? notice("bad", "The in-process scheduler is not running. Start it with KVI_SCHEDULER_ENABLED=true, or use the OS scheduler/n8n trigger in docs/SCHEDULER.md.") : ""}
      </section>`;
  }

  // ------------------------------------------------------------ privacy
  async function renderPrivacy() {
    const s = await api("GET", "/api/settings");
    content().innerHTML = `<div class="page-head"><h2>Privacy &amp; retention</h2></div>
      ${notice("info", "Principles: collect only what school management needs; redact personal identifiers in summaries; do not record health, counselling or family details in routine reports; no automated disciplinary, admission, grading or employment decisions.")}
      <div class="two-col">
        <section class="section"><h3>Retention</h3>
          <p>Raw WhatsApp message text and Facebook comments older than <b>${esc(s.retention_days)}</b> days are deleted by the purge action. Daily reports, action items and delivery logs are kept as the school's record.</p>
          ${can("admin") ? `<form id="ret-form" class="stack"><label>Retention days (30–3650) <input type="number" name="retention_days" min="30" max="3650" value="${esc(s.retention_days)}"></label>
            <label class="inline-check"><input type="checkbox" name="redact" ${s.redact_in_summaries ? "checked" : ""}> Redact personal identifiers in summaries (recommended)</label>
            <div class="btn-row"><button class="btn primary" type="submit">Save settings</button>
            <button class="btn danger" type="button" id="purge-btn">Run retention purge now</button></div></form>` : ""}
        </section>
        <section class="section"><h3>Recipients</h3>
          <p>Daily report: <b>${esc(s.report_recipient)}</b></p>
          <p>Backup recipient: ${esc(s.backup_recipient)}</p>
          <p class="fine">Backup recipient is disabled until KVI_BACKUP_RECIPIENT is set.</p>
        </section>
      </div>`;
    const f = $("#ret-form");
    if (f) f.onsubmit = async (e) => {
      e.preventDefault();
      const fd = new FormData(f);
      try { await api("PUT", "/api/settings", { retention_days: Number(fd.get("retention_days")), redact_in_summaries: f.redact.checked }); toast("Settings saved."); }
      catch (err) { toast("Save failed: " + err.message); }
    };
    const pb = $("#purge-btn");
    if (pb) pb.onclick = async () => {
      const ok = await confirmDialog("Run retention purge?", "<p>This permanently deletes raw message text and comments older than the retention period. This cannot be undone.</p>", "Purge", true);
      if (!ok) return;
      try { const r = await api("POST", "/api/retention/purge", { confirm: true }); toast(`Purged: ${r.messages_deleted} messages, ${r.fb_comments_deleted} comments.`, 6000); }
      catch (err) { toast("Purge failed: " + err.message); }
    };
  }

  // ------------------------------------------------------------ users
  async function renderUsers() {
    const users = await api("GET", "/api/users");
    content().innerHTML = `<div class="page-head"><h2>User management</h2><button class="btn primary" id="new-user">Add user</button></div>
      ${notice("info", "Roles: <b>viewer</b> (read-only) · <b>staff</b> (imports, redacted archive) · <b>leadership</b> (reports, actions, email logs) · <b>admin</b> (users, settings, resend, purge). Passwords must be at least 12 characters.")}
      <div class="table-wrap"><table><caption class="sr-only">Users</caption><thead><tr><th scope="col">Username</th><th scope="col">Name</th><th scope="col">Role</th><th scope="col">Active</th><th scope="col">Change</th></tr></thead><tbody>
      ${users.map((u) => `<tr><td>${esc(u.username)}</td><td>${esc(u.full_name)}</td><td>${esc(u.role)}</td><td>${u.is_active ? "Yes" : "No"}</td>
        <td><div class="btn-row"><select aria-label="Role for ${esc(u.username)}" data-role="${esc(u.id)}">${["viewer", "staff", "leadership", "admin"].map((r) => `<option ${r === u.role ? "selected" : ""}>${r}</option>`).join("")}</select>
        <button class="btn" data-toggle="${esc(u.id)}" data-active="${u.is_active}">${u.is_active ? "Disable" : "Enable"}</button></div></td></tr>`).join("")}
      </tbody></table></div>`;
    $("#new-user").onclick = () => {
      const html = `<form id="nu" class="stack">
        <label>Username <input name="username" required pattern="[A-Za-z0-9_.\\-]{3,80}" maxlength="80"></label>
        <label>Full name <input name="full_name" maxlength="160"></label>
        <label>Role <select name="role">${["viewer", "staff", "leadership", "admin"].map((r) => `<option>${r}</option>`).join("")}</select></label>
        <label>Temporary password (≥12 characters) <input name="password" type="password" required minlength="12" maxlength="256" autocomplete="new-password"></label></form>`;
      confirmDialog("Add user", html, "Create").then(async (ok) => {
        if (!ok) return;
        const f = $("#nu"); if (!f.reportValidity()) return;
        const fd = new FormData(f);
        try { await api("POST", "/api/users", Object.fromEntries(fd.entries())); toast("User created."); route(); }
        catch (e) { toast("Not created: " + e.message, 6000); }
      });
    };
    content().querySelectorAll("[data-role]").forEach((s) => s.onchange = async () => {
      try { await api("PATCH", `/api/users/${s.dataset.role}`, { role: s.value }); toast("Role updated."); }
      catch (e) { toast(e.message, 6000); route(); }
    });
    content().querySelectorAll("[data-toggle]").forEach((b) => b.onclick = async () => {
      try { await api("PATCH", `/api/users/${b.dataset.toggle}`, { is_active: b.dataset.active !== "true" }); toast("User updated."); route(); }
      catch (e) { toast(e.message, 6000); }
    });
  }

  // ------------------------------------------------------------ system health
  async function renderSystem() {
    const [sys, health] = await Promise.all([api("GET", "/api/system"), api("GET", "/api/health")]);
    content().innerHTML = `<div class="page-head"><h2>System health &amp; troubleshooting</h2></div>
      <div class="grid">
        ${kpi("Service", health.status === "ok" ? "OK" : "Degraded", health.status === "ok" ? "ok" : "alert")}
        ${kpi("Database", sys.database)}
        ${kpi("Scheduler", sys.scheduler.running ? "Running" : "Stopped", sys.scheduler.running ? "ok" : "alert")}
        ${kpi("Email", sys.email.configured ? "Configured" : "Not configured", sys.email.configured ? "ok" : "warn")}
        ${kpi("Facebook", sys.facebook.configured ? "Configured" : "Not configured", sys.facebook.configured ? "ok" : "warn")}
        ${kpi("AI analysis", sys.ai.configured ? "Hosted model" : "Rules engine", "")}
      </div>
      <section class="section"><h3>Configuration checks</h3>
        <div class="table-wrap"><table><caption class="sr-only">Configuration checks</caption><thead><tr><th scope="col">Item</th><th scope="col">Status</th><th scope="col">Detail</th></tr></thead><tbody>
        ${sys.config_checks.map((c) => `<tr><td>${esc(c.item)}</td><td>${statusChip(c.ok ? "OK" : "Action needed", c.ok ? "ok" : "warn")}</td><td class="evidence">${esc(c.detail)}</td></tr>`).join("")}
        </tbody></table></div></section>
      <section class="section"><h3>Recent failures</h3>
        ${sys.recent_failures.length ? `<ul class="clean">${sys.recent_failures.map((f) => `<li>${esc(f.at)} — <b>${esc(f.source)}</b> (${esc(f.kind)}): ${esc(f.error)}</li>`).join("")}</ul>` : notice("ok", "No recent failed imports or syncs.")}
      </section>
      <section class="section"><h3>Troubleshooting</h3><ul class="clean">
        <li>Report not delivered? Check Email delivery logs for the provider response; confirm KVI_SMTP_* values.</li>
        <li>Group shows “no data”? Export that group from WhatsApp and upload it, or check the file name matches the registered group.</li>
        <li>Facebook “not connected”? Check the token and permissions in docs/META_FACEBOOK_SETUP.md; manual import still works.</li>
        <li>Nepali text in PDF shows “?”? Set KVI_PDF_FONT_PATH to a Devanagari-capable font. The HTML email is unaffected.</li>
      </ul></section>`;
  }

  // ------------------------------------------------------------ events
  function bindEvents() {
    $("#login-form").onsubmit = async (e) => {
      e.preventDefault();
      const f = new FormData(e.target);
      $("#login-error").textContent = "";
      try {
        state.user = await api("POST", "/api/auth/login", { username: f.get("username"), password: f.get("password") });
        e.target.reset();
        state.meta = await api("GET", "/api/meta");
        state.today = (await api("GET", "/api/dashboard")).today_npt;
        showApp();
        if (location.hash === "" || location.hash === "#/overview") { location.hash = "#/overview"; route(); }
        else route();
      } catch (err) {
        $("#login-error").textContent = err.message === "401" ? "" : err.message;
      }
    };
    $("#logout-btn").onclick = async () => {
      try { await api("POST", "/api/auth/logout", {}); } catch (_) { /* ignore */ }
      state.user = null; location.hash = ""; showLogin("You have signed out.");
    };
    $("#nav-toggle").onclick = () => {
      const open = $("#sidebar").classList.toggle("open");
      $("#nav-toggle").setAttribute("aria-expanded", String(open));
    };
    window.addEventListener("hashchange", route);
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && $("#sidebar").classList.contains("open")) $("#nav-toggle").click(); });
  }

  bindEvents();
  boot();
})();
