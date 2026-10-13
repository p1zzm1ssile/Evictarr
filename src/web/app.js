"use strict";

// ---------- Helpers ----------

const view = document.getElementById("view");

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", "X-Evictarr": "1", ...(options.headers || {}) },
  });
  if (response.status === 401) {
    window.location.href = "/login";
    throw new Error("Please log in");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.error || `Request failed (${response.status})`);
    error.data = data;
    throw error;
  }
  return data;
}

// Builds elements. Text always goes in as text, never as HTML.
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key === "style") node.style.cssText = value; // CSP allows styles set from script, not style attributes
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (value === true) node.setAttribute(key, "");
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function age(minutes) {
  if (minutes < 60) return `${minutes}m`;
  if (minutes < 60 * 48) return `${Math.round(minutes / 60)}h`;
  return `${Math.round(minutes / 1440)}d`;
}

function ago(seconds) {
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  return `${Math.round(seconds / 3600)}h ago`;
}

let refreshTimer = null;
function every(ms, fn) {
  clearInterval(refreshTimer);
  refreshTimer = setInterval(fn, ms);
}

// ---------- Header ----------

async function refreshHealth() {
  const pill = document.getElementById("health");
  const text = document.getElementById("health-text");
  try {
    const h = await api("/api/status");
    pill.className = "pill " + (h.healthy ? "ok" : "bad");
    text.textContent = h.healthy ? "Healthy" : "Needs attention";
    const lines = Object.entries(h.checks).map(([name, c]) =>
      `${name}: ${c.summary}${c.last_run ? ` (${ago(Math.round(Date.now() / 1000 - c.last_run))})` : ""}`);
    pill.title = [h.client && h.client.name ? `Clients: ${h.client.name}` : "", ...h.problems, ...lines].filter(Boolean).join("\n");
  } catch {
    pill.className = "pill bad";
    text.textContent = "Not responding";
  }
}

document.getElementById("logout").addEventListener("click", async () => {
  await api("/api/logout", { method: "POST", body: "{}" }).catch(() => {});
  window.location.href = "/login";
});

api("/api/session").then((s) => {
  document.getElementById("whoami").textContent = s.user || "";
  if (s.user === "(local network)") document.getElementById("logout").textContent = "Log in";
});

// ---------- Downloads (start page) ----------

const STATE_BADGE = {
  stalled: ["Stalled", "bad"],
  error: ["Error", "bad"],
  processing: ["Downloading", "info"],
  finished: ["Finished", "ok"],
  queued: ["Queued", ""],
  paused: ["Paused", ""],
  unknown: ["Unknown", ""],
};

function fileBadge(f, tracked) {
  // Evictarr only acts on downloads Sonarr/Radarr are tracking
  if ((f.blocked || f.skipped) && !tracked) {
    return el("span", { class: "badge", title: "Not tracked by Sonarr or Radarr, so Evictarr leaves it alone",
      text: `Matches ${f.blocked ? "block" : "skip"} list, left alone` });
  }
  if (f.blocked) return el("span", { class: "badge bad", text: `Blocked ${f.blocked}` });
  if (f.skipped && f.wanted) return el("span", { class: "badge warn", text: `Will be skipped (${f.skipped})` });
  if (!f.wanted) return el("span", { class: "badge", text: "Not downloading" });
  return null;
}

async function loadFiles(row, download) {
  const holder = row.nextElementSibling.querySelector("td");
  holder.replaceChildren(el("div", { class: "muted small", text: "Loading files…" }));
  try {
    const { files } = await api(`/api/files?id=${encodeURIComponent(download.id)}`);
    if (!files.length) {
      holder.replaceChildren(el("div", { class: "muted small", text: "No file list yet (waiting for the torrent's metadata)." }));
      return;
    }
    holder.replaceChildren(el("ul", { class: "files" },
      files.map((f) => el("li", { class: f.wanted ? "" : "unwanted" },
        el("span", { class: "fname mono", text: f.name }), fileBadge(f, !!download.tracked_by)))));
  } catch (e) {
    holder.replaceChildren(el("div", { class: "error-text", text: e.message }));
  }
}

async function showDownloads() {
  const search = el("input", { type: "search", placeholder: "Search downloads", "aria-label": "Search downloads" });
  const filter = el("select", { "aria-label": "Show" },
    el("option", { value: "all", text: "All downloads" }),
    el("option", { value: "tracked", text: "Tracked by Sonarr/Radarr" }),
    el("option", { value: "stalled", text: "Stalled or errored" }));
  const expandAll = el("button", { type: "button", text: "Show all files" });
  const refresh = el("button", { type: "button", text: "Refresh" });
  const runNow = el("button", { type: "button", text: "Run checks now", title: "Run every purge now instead of waiting for the next scheduled check" });
  const selectedText = el("span", { class: "muted" });
  const removeButton = el("button", { type: "button", class: "danger", text: "Remove…", disabled: true });
  const clearButton = el("button", { type: "button", class: "link", text: "Clear selection" });
  const actionBar = el("div", { class: "toolbar actionbar", hidden: true }, selectedText, removeButton, clearButton);
  const selected = new Set();
  const summary = el("p", { class: "muted small" });
  const notices = el("div");
  const indexersBox = el("div");
  const table = el("table");

  view.replaceChildren(
    el("h1", { text: "Downloads" }),
    notices,
    el("div", { class: "toolbar" },
      el("div", { style: "flex:1;min-width:200px" }, search),
      el("div", { style: "width:220px" }, filter), expandAll, refresh, runNow),
    actionBar,
    el("div", { class: "panel", style: "padding:0;overflow-x:auto" }, table),
    summary,
    indexersBox);

  let downloads = [];

  function updateSelection() {
    // Forget anything that's no longer in the list
    const ids = new Set(downloads.map((d) => d.id));
    for (const id of [...selected]) if (!ids.has(id)) selected.delete(id);
    actionBar.hidden = selected.size === 0;
    removeButton.disabled = selected.size === 0;
    selectedText.textContent = `${selected.size} selected`;
    const all = table.querySelector("input.select-all");
    const boxes = [...table.querySelectorAll("input.select-row")];
    if (all) {
      all.checked = boxes.length > 0 && boxes.every((b) => b.checked);
      all.indeterminate = !all.checked && boxes.some((b) => b.checked);
    }
  }

  function render() {
    const term = search.value.trim().toLowerCase();
    const shown = downloads.filter((d) =>
      (!term || d.name.toLowerCase().includes(term) || (d.category || "").toLowerCase().includes(term)) &&
      (filter.value !== "tracked" || d.tracked_by) &&
      (filter.value !== "stalled" || d.state === "stalled" || d.state === "error"));

    const selectAll = el("input", { type: "checkbox", class: "select-all", "aria-label": "Select all shown downloads",
      onchange: () => {
        for (const d of shown) selectAll.checked ? selected.add(d.id) : selected.delete(d.id);
        table.querySelectorAll("input.select-row").forEach((b) => (b.checked = selectAll.checked));
        updateSelection();
      } });
    const head = el("thead", {}, el("tr", {},
      el("th", { class: "check" }, selectAll),
      el("th", { text: "Name" }), el("th", { text: "Client", class: "hide-small" }), el("th", { text: "Category" }),
      el("th", { text: "Status" }), el("th", { text: "Tracked by", class: "hide-small" }), el("th", { text: "Age", class: "hide-small" })));
    const body = el("tbody");

    for (const d of shown) {
      const [label, tone] = STATE_BADGE[d.state] || STATE_BADGE.unknown;
      const box = el("input", { type: "checkbox", class: "select-row", checked: selected.has(d.id), "aria-label": `Select ${d.name}`,
        onclick: (e) => e.stopPropagation(),
        onchange: () => { box.checked ? selected.add(d.id) : selected.delete(d.id); updateSelection(); } });
      const row = el("tr", { class: "download", tabindex: "0", "aria-expanded": "false" },
        el("td", { class: "check", onclick: (e) => e.stopPropagation() }, box),
        el("td", { class: "name" }, el("span", { class: "caret", text: "▸" }), d.name),
        el("td", { class: "hide-small", text: d.client }),
        el("td", { text: d.category || "—" }),
        el("td", {}, el("span", { class: `badge ${tone}`, text: label })),
        el("td", { class: "hide-small" }, d.tracked_by ? `${d.tracked_by}${d.indexer ? ` · ${d.indexer}` : ""}` : el("span", { class: "muted", text: "—" })),
        el("td", { class: "hide-small", text: age(d.age_minutes) }));
      const detail = el("tr", { hidden: true }, el("td", { colspan: "7" }));
      const toggle = () => {
        const open = detail.hidden;
        detail.hidden = !open;
        row.classList.toggle("open", open);
        row.setAttribute("aria-expanded", String(open));
        if (open && !detail.dataset.loaded) { detail.dataset.loaded = "1"; loadFiles(row, d); }
      };
      row.addEventListener("click", toggle);
      row.addEventListener("keydown", (e) => {
        if (e.target !== row) return;
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
      });
      row._toggle = toggle;
      body.append(row, detail);
    }

    if (!shown.length) {
      body.append(el("tr", {}, el("td", { colspan: "7", class: "empty",
        text: downloads.length ? "Nothing matches." : "No downloads in your download clients right now." })));
    }
    table.replaceChildren(head, body);
    summary.textContent = `${shown.length} of ${downloads.length} downloads. Click a download to see its files, or tick downloads to remove them.`;
    updateSelection();
  }

  function confirmRemove() {
    const chosen = downloads.filter((d) => selected.has(d.id));
    const tracked = chosen.filter((d) => d.tracked_by).length;
    const deleteFiles = el("input", { type: "checkbox", checked: true });
    const blocklist = el("input", { type: "checkbox", checked: tracked > 0, disabled: tracked === 0 });
    const result = el("div", { class: "result", role: "status" });
    const go = el("button", { type: "button", class: "primary danger-fill", text: `Remove ${chosen.length}` });
    const cancel = el("button", { type: "button", text: "Cancel" });
    const dialog = el("dialog", { class: "modal", "aria-labelledby": "remove-title" },
      el("h2", { id: "remove-title", text: `Remove ${chosen.length} download${chosen.length === 1 ? "" : "s"}?` }),
      el("ul", { class: "modal-list" }, chosen.slice(0, 8).map((d) => el("li", { class: "mono", text: d.name })),
        chosen.length > 8 ? el("li", { class: "muted", text: `…and ${chosen.length - 8} more` }) : null),
      el("label", { class: "switch" }, deleteFiles, el("span", { class: "track" }),
        el("span", { class: "text" }, "Delete their files", el("div", { class: "help", text: "Turn off to remove them from the download client but keep what's been downloaded." }))),
      el("label", { class: "switch" }, blocklist, el("span", { class: "track" }),
        el("span", { class: "text" }, "Blocklist and search for a replacement",
          el("div", { class: "help", text: tracked
            ? `${tracked} of these ${tracked === 1 ? "is" : "are"} tracked by Sonarr/Radarr. They'll be added to the blocklist first, so a different release is grabbed.`
            : "None of these are tracked by Sonarr or Radarr, so there's nothing to blocklist." }))),
      result,
      el("div", { class: "modal-actions" }, cancel, go));
    document.body.append(dialog);
    cancel.addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => dialog.remove());
    go.addEventListener("click", async () => {
      go.disabled = cancel.disabled = true;
      result.className = "result muted";
      result.textContent = "Removing…";
      try {
        const r = await api("/api/downloads/remove", { method: "POST", body: JSON.stringify({
          ids: chosen.map((d) => d.id), delete_files: deleteFiles.checked, blocklist: blocklist.checked && !blocklist.disabled }) });
        const parts = [`Removed ${r.removed}`];
        if (r.blocklisted) parts.push(`blocklisted ${r.blocklisted}`);
        if (r.missing) parts.push(`${r.missing} already gone`);
        selected.clear();
        dialog.close();
        await load();
        // After the refresh, which clears earlier messages
        notices.prepend(el("div", { class: `notice ${r.problems.length ? "bad" : "ok"}` },
          parts.join(", ") + ".", r.problems.length ? el("div", { class: "small", text: r.problems.join("; ") }) : null));
      } catch (e) {
        result.className = "result bad";
        result.textContent = e.message;
        go.disabled = cancel.disabled = false;
      }
    });
    dialog.showModal();
  }

  async function load() {
    refresh.disabled = true;
    try {
      const data = await api("/api/downloads");
      downloads = data.downloads;
      notices.replaceChildren();
      if (!data.clients.length) {
        notices.append(el("div", { class: "notice warn" }, "No download client is set up yet. ",
          el("a", { href: "#/settings/clients", text: "Choose one in Settings > Download clients" }), "."));
      }
      for (const [client, error] of Object.entries(data.errors)) {
        notices.append(el("div", { class: "notice bad", text: `${client}: ${error}` }));
      }
      render();
    } catch (e) {
      notices.replaceChildren(el("div", { class: "notice bad", text: e.message }));
    } finally {
      refresh.disabled = false;
    }
  }

  async function loadIndexers() {
    try {
      const { sources } = await api("/api/indexers");
      indexersBox.replaceChildren(...sources.map((s) => el("div", { class: "panel" },
        el("h2", { text: `${s.source} indexers` }),
        s.error ? el("div", { class: "error-text", text: s.error }) :
          s.indexers.length ? el("div", { class: "chips" }, s.indexers.map((i) =>
            el("span", { class: `badge ${!i.enabled ? "" : i.ok ? "ok" : "bad"}`, title: i.problem || (i.enabled ? "Working" : "Turned off"),
              text: `${i.name}${!i.enabled ? " (off)" : i.ok ? "" : " (failing)"}` })))
            : el("div", { class: "muted small", text: "No indexers found." }))));
    } catch { /* indexers are optional */ }
  }

  search.addEventListener("input", render);
  filter.addEventListener("change", render);
  refresh.addEventListener("click", load);
  removeButton.addEventListener("click", confirmRemove);
  clearButton.addEventListener("click", () => {
    selected.clear();
    table.querySelectorAll("input.select-row").forEach((b) => (b.checked = false));
    updateSelection();
  });
  runNow.addEventListener("click", async () => {
    runNow.disabled = true;
    try {
      await api("/api/checks/run", { method: "POST", body: "{}" });
      notices.replaceChildren(el("div", { class: "notice ok", text: "Running every check now. See Logs > Actions for what they do." }));
      setTimeout(() => { load(); refreshHealth(); }, 4000);
    } catch (e) {
      notices.replaceChildren(el("div", { class: "notice bad", text: e.message }));
    } finally {
      setTimeout(() => (runNow.disabled = false), 4000);
    }
  });
  expandAll.addEventListener("click", () => {
    for (const row of table.querySelectorAll("tr.download:not(.open)")) row._toggle();
  });

  await load();
  loadIndexers();
  every(30000, load);
}

// ---------- Logs ----------

async function showLogs() {
  let kind = "all";
  const box = el("div", { class: "log", role: "log", "aria-live": "polite" });
  const search = el("input", { type: "search", placeholder: "Search logs", "aria-label": "Search logs" });
  const auto = el("input", { type: "checkbox", checked: true });
  const buttons = {};
  const segmented = el("div", { class: "segmented", role: "group", "aria-label": "Show" },
    ["all", "issues", "actions"].map((k) => (buttons[k] = el("button", {
      type: "button", class: k === kind ? "active" : "",
      text: { all: "All", issues: "Issues", actions: "Actions" }[k],
      onclick: () => { kind = k; Object.values(buttons).forEach((b) => b.classList.remove("active")); buttons[k].classList.add("active"); load(true); },
    }))));

  view.replaceChildren(
    el("h1", { text: "Logs" }),
    el("p", { class: "muted small", text: "Issues shows errors and warnings. Actions shows everything Evictarr removed, blocklisted or skipped." }),
    el("div", { class: "toolbar" }, segmented,
      el("div", { style: "flex:1;min-width:180px" }, search),
      el("label", { class: "chip" }, auto, "Auto refresh"),
      el("a", { class: "button", href: "/api/logs/download", text: "Download all logs" })),
    box);

  let lines = [];
  function render(scroll) {
    const term = search.value.trim().toLowerCase();
    const shown = lines.filter((l) => !term || l.message.toLowerCase().includes(term));
    const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
    box.replaceChildren(...(shown.length ? shown.map((l) => el("div", { class: "line" },
      el("span", { class: "time", text: l.time }), el("span", { class: `lvl lvl-${l.level}`, text: l.level }), l.message))
      : [el("div", { class: "empty", text: kind === "issues" ? "No issues. All good!" : "Nothing to show yet." })]));
    if (scroll || atBottom) box.scrollTop = box.scrollHeight;
  }

  async function load(scroll) {
    try {
      lines = (await api(`/api/logs?filter=${kind}`)).lines;
      render(scroll);
    } catch (e) {
      box.replaceChildren(el("div", { class: "error-text", text: e.message }));
    }
  }

  search.addEventListener("input", () => render(false));
  await load(true);
  every(5000, () => { if (auto.checked) load(false); });
}

// ---------- Settings ----------

let settings = null;

function fieldInput(field, value, onChange) {
  const id = `f-${field.key}`;
  const help = field.help ? el("div", { class: "help", text: field.help }) : null;
  const error = el("div", { class: "error-text", id: `${id}-error` });

  if (field.type === "bool") {
    const input = el("input", { type: "checkbox", id, checked: !!value, onchange: onChange });
    return { node: el("label", { class: "switch", for: id }, input, el("span", { class: "track" }),
      el("span", { class: "text" }, field.label, help, error)), get: () => input.checked, input };
  }

  if (field.type === "files") {
    const parts = String(value || "").split(",").map((p) => p.trim()).filter(Boolean);
    const boxes = Object.entries(settings.groups).map(([group, list]) => {
      const box = el("input", { type: "checkbox", checked: parts.includes(`@${group}`), onchange: onChange });
      return { group, box, node: el("label", { class: "chip", title: list.replaceAll(",", ", ") }, box, group.replace("-", " ")) };
    });
    const custom = el("input", { type: "text", id, placeholder: "Other extensions, e.g. arj, lnk, mkv.lnk",
      value: parts.filter((p) => !p.startsWith("@")).join(", "), oninput: onChange });
    return {
      node: el("div", { class: "field", style: "margin-bottom:1rem" },
        el("span", { class: "label", style: "font-weight:600;display:block;margin-bottom:0.4rem", text: field.label }),
        el("div", { class: "chips" }, boxes.map((b) => b.node)), custom, help,
        el("div", { class: "help", text: "Hover a group to see what's in it." }), error),
      get: () => [...boxes.filter((b) => b.box.checked).map((b) => `@${b.group}`),
        ...custom.value.split(",").map((p) => p.trim()).filter(Boolean)].join(","),
    };
  }

  if (field.type === "languages") {
    const chosen = String(value || "").split(",").map((p) => p.trim()).filter(Boolean);
    const boxes = Object.entries(settings.languages).map(([code, name]) => {
      const box = el("input", { type: "checkbox", checked: chosen.includes(code), onchange: onChange });
      return { code, box, node: el("label", { class: "chip" }, box, name) };
    });
    return {
      node: el("div", { class: "field", style: "margin-bottom:1rem" },
        el("span", { class: "label", style: "font-weight:600;display:block;margin-bottom:0.4rem", text: field.label }),
        el("div", { class: "chips" }, boxes.map((b) => b.node)), help, error),
      get: () => boxes.filter((b) => b.box.checked).map((b) => b.code).join(","),
    };
  }

  let input;
  if (field.type === "select") {
    input = el("select", { id, onchange: onChange }, field.options.map((o) => el("option", { value: o, text: o, selected: o === value })));
  } else if (field.type === "secret") {
    input = el("input", { type: "password", id, autocomplete: "new-password", oninput: onChange,
      placeholder: value && value.set ? "•••••••• saved (type to replace)" : "Not set" });
  } else {
    input = el("input", { type: field.type === "int" ? "number" : "text", id, value: value ?? "", oninput: onChange,
      min: field.min, max: field.max, placeholder: field.placeholder, spellcheck: "false" });
  }
  return {
    node: el("label", { class: "field", for: id }, el("span", { class: "label", text: field.label }), input, help, error),
    get: () => field.type === "secret" ? (input.value === "" ? null : input.value)
      : field.type === "int" ? input.value : input.value,
    input,
  };
}

const TESTABLE = { sonarr: "sonarr", radarr: "radarr", qbittorrent: "qbittorrent", rdtclient: "rdtclient",
  deluge: "deluge", transmission: "transmission", sabnzbd: "sabnzbd", prowlarr: "prowlarr", jackett: "jackett" };

async function showSettings(tab) {
  if (!settings) settings = await api("/api/settings");
  if (!settings.tabs[tab]) tab = "general";

  const fields = settings.fields.filter((f) => f.tab === tab);
  const getters = {};
  const status = el("span", { class: "muted small", role: "status" });
  let dirty = false;
  const markDirty = () => { dirty = true; status.className = "warn small"; status.textContent = "Unsaved changes"; status.style.color = "var(--warn)"; };

  const formValues = () => Object.fromEntries(Object.entries(getters).map(([k, g]) => [k, g()]));

  async function test(target, result, button) {
    button.disabled = true;
    result.className = "result muted";
    result.textContent = "Testing…";
    try {
      const r = await api("/api/test", { method: "POST", body: JSON.stringify({ target, values: formValues() }) });
      result.className = `result ${r.ok ? "ok" : "bad"}`;
      result.textContent = (r.ok ? "✓ " : "✗ ") + r.message;
    } catch (e) {
      result.className = "result bad";
      result.textContent = "✗ " + e.message;
    } finally {
      button.disabled = false;
    }
  }

  function testButton(target) {
    const result = el("span", { class: "result" });
    const button = el("button", { type: "button", text: "Test connection" });
    button.addEventListener("click", () => test(target, result, button));
    return el("div", { class: "card-actions" }, button, result);
  }

  // Group fields into sections; toggle groups (clients, indexers) become cards
  const sections = [];
  for (const field of fields) {
    const key = field.group || field.section;
    let section = sections.find((s) => s.key === key);
    if (!section) sections.push(section = { key, title: field.section, group: field.group, fields: [] });
    section.fields.push(field);
  }

  const content = sections.map((section) => {
    const rendered = section.fields.map((f) => {
      const input = fieldInput(f, settings.values[f.key], markDirty);
      getters[f.key] = input.get;
      return { field: f, ...input };
    });

    if (section.group) {
      const toggle = rendered.find((r) => r.field.toggle);
      const rest = rendered.filter((r) => r !== toggle);
      const card = el("div", { class: "card" + (toggle.get() ? "" : " off") },
        toggle.node,
        el("div", { class: "card-body" },
          el("div", { class: "grid-2" }, rest.map((r) => r.node)),
          TESTABLE[section.group] ? testButton(TESTABLE[section.group]) : null));
      toggle.input.addEventListener("change", () => card.classList.toggle("off", !toggle.input.checked));
      return card;
    }

    const isConnection = (tab === "sonarr" || tab === "radarr") && section.title === "Connection";
    return el("div", { class: "panel" },
      el("h2", { text: section.title }),
      el("div", { class: section.fields.some((f) => f.type === "files" || f.type === "languages") ? "" : "grid-2" }, rendered.map((r) => r.node)),
      isConnection ? testButton(tab) : null);
  });

  if (tab === "clients") {
    content.unshift(el("p", { class: "muted", text: "Tick every download client you use. Evictarr checks all of them, and keeps working with the others if one is down." }));
  }
  if (tab === "indexers") {
    content.unshift(el("p", { class: "muted", text: "Optional. With Prowlarr or Jackett connected, the Downloads page shows which indexers are working or failing, and the logs name the indexer a rejected release came from." }));
  }
  if (tab === "general") content.push(...accountPanels());

  const saveButton = el("button", { class: "primary", type: "button", text: `Save ${settings.tabs[tab]}` });
  saveButton.addEventListener("click", async () => {
    saveButton.disabled = true;
    view.querySelectorAll(".error-text[id$='-error']").forEach((e) => (e.textContent = ""));
    try {
      const r = await api("/api/settings", { method: "PUT", body: JSON.stringify({ values: formValues() }) });
      settings.values = r.values;
      dirty = false;
      status.style.color = "var(--ok)";
      status.textContent = "✓ Saved. Changes are in effect now.";
      refreshHealth();
      setTimeout(refreshHealth, 3000);
    } catch (e) {
      status.style.color = "var(--bad)";
      const errors = (e.data && e.data.errors) || {};
      for (const [key, message] of Object.entries(errors)) {
        const box = document.getElementById(`f-${key}-error`);
        if (box) box.textContent = message;
      }
      status.textContent = Object.keys(errors).length ? "Please fix the highlighted settings." : e.message;
    } finally {
      saveButton.disabled = false;
    }
  });

  view.replaceChildren(
    el("h1", { text: "Settings" }),
    el("div", { class: "tabs", role: "tablist" }, Object.entries(settings.tabs).map(([key, label]) =>
      el("button", { type: "button", role: "tab", class: key === tab ? "active" : "", "aria-selected": String(key === tab), text: label,
        onclick: () => {
          if (dirty && !confirm("You have unsaved changes on this tab. Leave without saving?")) return;
          location.hash = `#/settings/${key}`;
        } }))),
    ...content,
    el("div", { class: "savebar" }, saveButton, status));

  window.onbeforeunload = () => (dirty ? true : undefined);
}

function accountPanels() {
  const current = el("input", { type: "password", autocomplete: "current-password" });
  const user = el("input", { type: "text", value: settings.username, autocomplete: "username" });
  const password = el("input", { type: "password", autocomplete: "new-password" });
  const confirmBox = el("input", { type: "password", autocomplete: "new-password" });
  const rules = el("ul", { class: "rules" });
  const result = el("div", { class: "result", role: "status" });
  const RULES = [
    ["At least 8 characters", (p) => p.length >= 8],
    ["An uppercase letter", (p) => /[A-Z]/.test(p)],
    ["A lowercase letter", (p) => /[a-z]/.test(p)],
    ["A number", (p) => /[0-9]/.test(p)],
    ["A special character, like ! ? # or @", (p) => /[^A-Za-z0-9]/.test(p)],
  ];
  const renderRules = () => rules.replaceChildren(...RULES.map(([t, c]) => el("li", { class: c(password.value) ? "met" : "", text: t })));
  password.addEventListener("input", renderRules);
  renderRules();

  const change = el("button", { type: "button", text: "Change password" });
  change.addEventListener("click", async () => {
    result.className = "result bad";
    const missing = RULES.filter(([, c]) => !c(password.value));
    if (missing.length) { result.textContent = "The new password still needs: " + missing.map(([t]) => t.toLowerCase()).join(", "); return; }
    if (password.value !== confirmBox.value) { result.textContent = "The new passwords don't match"; return; }
    change.disabled = true;
    try {
      await api("/api/password", { method: "POST", body: JSON.stringify({ current: current.value, username: user.value.trim(), password: password.value }) });
      result.className = "result ok";
      result.textContent = "✓ Password changed. Other devices have been logged out.";
      settings.username = user.value.trim();
      current.value = password.value = confirmBox.value = "";
      renderRules();
    } catch (e) {
      result.textContent = e.message;
    } finally {
      change.disabled = false;
    }
  });

  return [
    el("div", { class: "panel" },
      el("h2", { text: "Account" }),
      el("div", { class: "notice warn small" },
        el("strong", { text: "Keep Evictarr on your home network. " }),
        "We don't recommend putting it behind a reverse proxy (Nginx Proxy Manager, SWAG, Traefik, Cloudflare Tunnel and the like) for access from outside. Use a VPN such as WireGuard or Tailscale instead. The local network login bypass above never applies to requests that come through a proxy."),
      el("div", { class: "grid-2" },
        el("label", { class: "field" }, el("span", { class: "label", text: "Username" }), user),
        el("label", { class: "field" }, el("span", { class: "label", text: "Current password" }), current),
        el("label", { class: "field" }, el("span", { class: "label", text: "New password" }), password, rules),
        el("label", { class: "field" }, el("span", { class: "label", text: "Confirm new password" }), confirmBox)),
      el("div", { class: "card-actions" }, change, result)),
    el("div", { class: "panel" },
      el("h2", { text: "Log files" }),
      el("p", { class: "muted small", text: "Everything Evictarr has logged, including older rotated files, as one zip. Handy for reporting a problem." }),
      el("a", { class: "button", href: "/api/logs/download", text: "Download all logs" })),
  ];
}

// ---------- Help & contact ----------

const PROJECT = "https://github.com/p1zzm1ssile/Evictarr";

function link(href, text) {
  return el("a", { href, text, target: "_blank", rel: "noopener noreferrer" });
}

async function showHelp() {
  const session = await api("/api/session");
  const version = session.version || "unknown";
  const issueBody = [
    "**What happened?**", "", "", "**What did you expect?**", "", "",
    "**Download client(s):** ", "", `Evictarr version: ${version}`,
    "", "(Attach the zip from Settings > General > Download all logs if you can. Check it doesn't contain anything private first.)",
  ].join("\n");
  const bugUrl = `${PROJECT}/issues/new?labels=bug&body=${encodeURIComponent(issueBody)}`;
  const ideaUrl = `${PROJECT}/issues/new?labels=enhancement&title=${encodeURIComponent("Idea: ")}`;

  view.replaceChildren(
    el("h1", { text: "Help & contact" }),
    el("div", { class: "panel" },
      el("h2", { text: "Get help or report a problem" }),
      el("p", { text: "Evictarr is supported through GitHub. Anyone can open an issue, and you'll get a reply there." }),
      el("div", { class: "toolbar" },
        el("a", { class: "button primary", href: bugUrl, target: "_blank", rel: "noopener noreferrer", text: "Report a problem" }),
        el("a", { class: "button", href: ideaUrl, target: "_blank", rel: "noopener noreferrer", text: "Suggest an idea" }),
        el("a", { class: "button", href: `${PROJECT}/issues`, target: "_blank", rel: "noopener noreferrer", text: "See open issues" })),
      el("h2", { text: "Before you report", style: "margin-top:1.25rem" }),
      el("ol", { class: "help-steps" },
        el("li", {}, "Check ", el("a", { href: "#/logs", text: "Logs" }), " and choose ", el("strong", { text: "Issues" }), ". The reason is often written there, such as a wrong password or an address that can't be reached."),
        el("li", {}, "Use ", el("strong", { text: "Test connection" }), " on each tab in ", el("a", { href: "#/settings/clients", text: "Settings" }), " to check every connection."),
        el("li", {}, "If you report a problem, attach your logs: ",
          el("a", { href: "/api/logs/download", text: "download all logs" }),
          ". Logs never contain your passwords or API keys, but they do list download names, so check you're happy to share them."))),
    el("div", { class: "panel" },
      el("h2", { text: "Contact me" }),
      el("p", {}, "For anything that doesn't belong on a public page, email ",
        el("a", { href: "mailto:p1zzm1ssilerepo@gmail.com?subject=Evictarr", text: "p1zzm1ssilerepo@gmail.com" }), ".")),
    el("div", { class: "panel" },
      el("h2", { text: "About Evictarr" }),
      el("dl", { class: "about" },
        el("dt", { text: "Version" }), el("dd", { class: "mono", text: version }),
        el("dt", { text: "Project" }), el("dd", {}, link(PROJECT, "github.com/p1zzm1ssile/Evictarr")),
        el("dt", { text: "What's new" }), el("dd", {}, link(`${PROJECT}/blob/main/CHANGELOG.md`, "Changelog")),
        el("dt", { text: "Guide" }), el("dd", {}, link(`${PROJECT}#readme`, "README: setup, every setting explained")),
        el("dt", { text: "Docker image" }), el("dd", { class: "mono", text: "ghcr.io/p1zzm1ssile/evictarr:latest" }))),
    el("div", { class: "panel" },
      el("h2", { text: "Thanks" }),
      el("p", {}, "Evictarr is built on ", link("https://github.com/steveharsant/purgarr", "Purgarr"),
        " by Steve Harsant, who created it. It's carried on here while Purgarr is inactive, with his history and licence kept."),
      el("p", { class: "muted small" }, "Evictarr includes Purgarr's code under the ",
        link("https://github.com/p1zzm1ssile/Evictarr/blob/main/LICENSE", "Boost Software License 1.0"), ".")),
  );
}

// ---------- Router ----------

async function route() {
  window.onbeforeunload = null;
  clearInterval(refreshTimer);
  const [, page = "", sub = ""] = (location.hash || "#/").split("/");
  const name = page || "downloads";
  document.querySelectorAll("nav.main a").forEach((a) => a.classList.toggle("active", a.dataset.page === name));
  try {
    if (name === "logs") await showLogs();
    else if (name === "settings") await showSettings(sub || "general");
    else if (name === "help") await showHelp();
    else await showDownloads();
  } catch (e) {
    view.replaceChildren(el("div", { class: "notice bad", text: e.message }));
  }
}

window.addEventListener("hashchange", route);
route();
refreshHealth();
setInterval(refreshHealth, 15000);
