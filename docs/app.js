// NetGuard buildy — frontend
(function () {
  "use strict";

  const POLL_MS = 30000; // co 30 s odpytujemy status
  const $ = (id) => document.getElementById(id);

  // ---------- helpers ----------
  function fmtSize(bytes) {
    if (!bytes) return "";
    const mb = bytes / (1024 * 1024);
    return mb >= 1 ? mb.toFixed(1) + " MB" : (bytes / 1024).toFixed(0) + " KB";
  }
  function fmtDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    return d.toLocaleDateString("pl-PL", { day: "2-digit", month: "2-digit", year: "numeric" });
  }
  function fmtDuration(sec) {
    if (!sec || sec < 0) return "";
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    if (m >= 60) return Math.floor(m / 60) + " h " + (m % 60) + " min";
    if (m > 0) return m + " min " + s + " s";
    return s + " s";
  }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  const DL_ICON =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></svg>';

  // ---------- builds ----------
  async function loadBuilds() {
    try {
      const res = await fetch("data/builds.json", { cache: "no-store" });
      if (!res.ok) throw new Error(res.status);
      const data = await res.json();
      renderBuilds(data);
    } catch (e) {
      $("buildsList").innerHTML = '<div class="empty">Nie udało się wczytać listy buildów (' + esc(e.message) + ").</div>";
    }
  }

  function renderBuilds(data) {
    const list = $("buildsList");
    const builds = data.builds || [];
    if (!builds.length) {
      list.innerHTML = '<div class="empty">Brak dostępnych buildów.</div>';
      return;
    }
    list.innerHTML = builds.map((b) => {
      const pro = b.proUnlocked
        ? '<span class="badge ok">Pro odblokowane</span>' : "";
      const sha = (b.sha256 || "").slice(0, 12);
      return (
        '<div class="item">' +
          '<div class="item-main">' +
            '<div class="item-title">v' + esc(b.version) + " · " + esc(b.label) + " " + pro + "</div>" +
            '<div class="item-sub">' + fmtSize(b.size) + " · " + fmtDate(b.date) + (sha ? " · sha256 " + esc(sha) + "…" : "") + "</div>" +
            (b.note ? '<div class="item-sub" style="font-family:inherit;color:var(--text-dim)">' + esc(b.note) + "</div>" : "") +
          "</div>" +
          '<a class="dl-btn" href="' + esc(b.file) + '" download>' + DL_ICON + "Pobierz APK</a>" +
        "</div>"
      );
    }).join("");

    $("buildsUpdated").textContent = "aktualne: " + fmtDate(data.updated);
    const src = data.source || {};
    $("buildsNote").textContent =
      "Źródło: " + (src.repo || "") + " · wersja " + (src.version || "") + " · licencja " + (src.license || "") +
      ". Wybierz build pod swój procesor: 64-bit (arm64) dla nowszych urządzeń, 32-bit (arm32) dla starszych.";
  }

  // ---------- configs ----------
  async function loadConfigs() {
    try {
      const res = await fetch("data/configs.json", { cache: "no-store" });
      if (!res.ok) throw new Error(res.status);
      const data = await res.json();
      renderConfigs(data);
    } catch (e) {
      $("configsList").innerHTML = '<div class="empty">Brak konfiguracji (' + esc(e.message) + ").</div>";
    }
  }

  function renderConfigs(data) {
    const list = $("configsList");
    const configs = data.configs || [];
    if (!configs.length) {
      list.innerHTML = '<div class="empty">Brak gotowych konfiguracji — wkrótce.</div>';
      return;
    }
    list.innerHTML = configs.map((c) => {
      const rules = c.rules ? Object.keys(c.rules).length : 0;
      return (
        '<div class="item">' +
          '<div class="item-main">' +
            '<div class="item-title">' + esc(c.name) + ' <span class="badge">' + rules + " reguł</span></div>" +
            '<div class="item-sub" style="font-family:inherit;color:var(--text-dim)">' + esc(c.device || "") + "</div>" +
            (c.desc ? '<div class="item-sub" style="font-family:inherit;color:var(--text-mute)">' + esc(c.desc) + "</div>" : "") +
          "</div>" +
          '<a class="dl-btn" href="' + esc(c.file) + '" download>' + DL_ICON + "Pobierz JSON</a>" +
        "</div>"
      );
    }).join("");
  }

  // ---------- status / progress ----------
  async function pollStatus() {
    try {
      const res = await fetch("data/status.json", { cache: "no-store" });
      if (!res.ok) throw new Error(res.status);
      const s = await res.json();
      renderStatus(s);
    } catch (e) {
      // status niedostępny — zostawiamy ostatni stan
    }
  }

  function renderStatus(s) {
    const pill = $("statusPill");
    const pillText = $("statusPillText");
    const line = $("bsLine");
    const meta = $("bsMeta");
    const prog = $("progress");
    const bar = $("progressBar");
    const updated = $("buildUpdated");

    updated.textContent = "odświeżono: " + fmtDate(s.updated);

    if (s.state === "building") {
      pill.dataset.state = "building";
      pillText.textContent = "Kompiluję…";
      line.textContent = s.step || "Trwa kompilacja…";

      const started = s.started ? new Date(s.started) : null;
      const last = s.lastBuild || {};
      const total = last.durationSec || 0;
      let parts = [];
      if (started && !isNaN(started)) {
        const elapsed = Math.max(0, (Date.now() - started.getTime()) / 1000);
        parts.push("min. od startu: " + fmtDuration(elapsed));
        if (total > 0) {
          const frac = Math.min(1, elapsed / total);
          bar.style.width = (frac * 100).toFixed(0) + "%";
          prog.hidden = false;
          const remaining = Math.max(0, total - elapsed);
          parts.push("szac. pozostało: ~" + fmtDuration(remaining));
        }
      }
      meta.textContent = parts.join("  ·  ");
    } else if (s.state === "error") {
      pill.dataset.state = "error";
      pillText.textContent = "Błąd builda";
      line.textContent = s.step || "Kompilacja zakończona błędem.";
      prog.hidden = true;
      meta.textContent = "";
    } else {
      pill.dataset.state = "idle";
      pillText.textContent = "Gotowe";
      prog.hidden = true;
      bar.style.width = "0%";
      const last = s.lastBuild || {};
      line.textContent = "Gotowe — brak aktywnego budowania.";
      if (last.finished) {
        meta.textContent = "Ostatni build: v" + (last.version || "") +
          " · " + fmtDate(last.finished) +
          (last.durationSec ? " · czas " + fmtDuration(last.durationSec) : "");
      }
    }
  }

  // ---------- how toggle ----------
  function initHow() {
    const btn = $("howToggle");
    const body = $("howBody");
    btn.addEventListener("click", () => {
      const open = btn.getAttribute("aria-expanded") === "true";
      btn.setAttribute("aria-expanded", String(!open));
      body.style.display = open ? "none" : "block";
    });
  }

  // ---------- init ----------
  function init() {
    initHow();
    loadBuilds();
    loadConfigs();
    pollStatus();
    setInterval(pollStatus, POLL_MS);
  }

  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", init);
  else init();
})();
