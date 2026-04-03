/* global PERI_PASCHA_DATA */

const DATA = window.PERI_PASCHA_DATA;

/* Audio section map — each entry: [startLine, endLine, filename] */
const AUDIO_SECTIONS = [
  [1, 25, "speech-1-25.mp3"],
  [26, 52, "speech-26-52.mp3"],
  [54, 82, "speech-54-82.mp3"],
  [84, 113, "speech-84-113.mp3"],
  [115, 142, "speech-115-142.mp3"],
  [144, 171, "speech-144-171.mp3"],
  [172, 202, "speech-172-202.mp3"],
  [204, 260, "speech-204-260.mp3"],
  [263, 291, "speech-263-291.mp3"],
  [294, 337, "speech-294-337.mp3"],
  [339, 385, "speech-339-385.mp3"],
  [388, 425, "speech-388-425.mp3"],
  [427, 470, "speech-427-470.mp3"],
  [473, 496, "speech-473-496.mp3"],
  [498, 555, "speech-498-555.mp3"],
  [558, 610, "speech-558-610.mp3"],
  [612, 671, "speech-612-671.mp3"],
  [674, 725, "speech-674-725.mp3"],
  [727, 783, "speech-727-783.mp3"],
  [784, 865, "speech-784-865.mp3"],
];

function audioForLine(sl) {
  for (const [start, end, file] of AUDIO_SECTIONS) {
    if (sl >= start && sl <= end) return { start, end, file: `./audio/${file}` };
  }
  return null;
}

/* Persistent audio state — survives detail panel re-renders */
const audioState = {
  el: new Audio(),
  file: null,
  playing: false,
  sectionStart: null,
  sectionEnd: null,
};

audioState.el.addEventListener("ended", () => {
  audioState.playing = false;
  updateAudioButton();
});

function toggleAudio(audioInfo) {
  const { el } = audioState;

  if (audioState.file === audioInfo.file) {
    // Same section — toggle play/pause
    if (audioState.playing) {
      el.pause();
      audioState.playing = false;
    } else {
      el.play();
      audioState.playing = true;
    }
  } else {
    // Different section — switch track
    el.src = audioInfo.file;
    el.play();
    audioState.file = audioInfo.file;
    audioState.playing = true;
    audioState.sectionStart = audioInfo.start;
    audioState.sectionEnd = audioInfo.end;
  }
  updateAudioButton();
}

function updateAudioButton() {
  const btn = document.querySelector(".audio-play-btn");
  if (!btn) return;
  if (audioState.playing) {
    btn.classList.add("is-playing");
    btn.innerHTML = "&#9646;&#9646;";
  } else {
    btn.classList.remove("is-playing");
    btn.innerHTML = "&#9654;";
  }
}

const state = {
  query: "",
  mode: "all",
  selectedSl: null,
};

const UI = {};

function normalizeSearch(text) {
  return String(text || "")
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/ς/g, "σ")
    .toLowerCase();
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function inferStatus(record) {
  if (record.status) return record.status;
  if (record.st) return record.st;
  const reading = String(record.reading || record.ana || record.src || "");
  if (reading === "[DELETED]") return "deleted";
  if (reading.startsWith("<UNCERTAIN:")) return "omitted";
  if (String(record.ana || "").startsWith("<UNCERTAIN:")) return "omitted";
  if (String(record.emd || "").includes("<UNCERTAIN:")) return "uncertain";
  if (Array.isArray(record.unc) && record.unc.length > 0) return "uncertain";
  return "normal";
}

function buildReading(record) {
  if (record.reading) return record.reading;
  if (record.ana === "[DELETED]") return "[DELETED]";
  if (record.status === "omitted" || record.st === "omitted") {
    return "[Omitted from continuous text]";
  }
  return record.ana || record.src;
}

function makeSearchBlob(record) {
  const tokText = Array.isArray(record.tok)
    ? record.tok.flat().join(" ")
    : "";
  const synText = record.syn ? JSON.stringify(record.syn) : "";
  const uncText = Array.isArray(record.unc) ? record.unc.join(" ") : "";
  return normalizeSearch([
    record.sl,
    record.src,
    record.ana || "",
    record.reading || "",
    record.lit || "",
    record.sm || "",
    record.emd || "",
    uncText,
    tokText,
    synText,
  ].join(" "));
}

function enrichRecord(record) {
  const enriched = { ...record };
  enriched.reading = buildReading(enriched);
  enriched.status = inferStatus(enriched);
  enriched.isDeleted = enriched.status === "deleted" || enriched.status === "omitted";
  enriched.isUncertain = enriched.status === "uncertain";
  enriched.hasEmendation = Boolean(enriched.emd);
  enriched.unc = Array.isArray(enriched.unc) ? enriched.unc : [];
  enriched.searchBlob = makeSearchBlob(enriched);
  enriched.snippet = enriched.isDeleted
    ? "OCR noise / omitted line"
    : enriched.reading;
  return enriched;
}

function fmtStat(value) {
  return Intl.NumberFormat("en-US").format(value);
}

function statCard(label, value, id) {
  const el = document.createElement("button");
  el.type = "button";
  el.className = "stat-card";
  if (id) el.dataset.jump = id;
  el.innerHTML = `<span class="stat-value">${escapeHtml(value)}</span><span class="stat-label">${escapeHtml(label)}</span>`;
  return el;
}

function badge(label, kind) {
  const span = document.createElement("span");
  span.className = `badge ${kind || ""}`.trim();
  span.textContent = label;
  return span;
}

function renderStats() {
  const { meta, qa } = DATA;
  const totalSourceLines = meta.total_source_lines ?? meta.totalSourceLines ?? 0;
  const completedRecords = meta.completed_nonblank_records ?? qa.record_count ?? qa.recordCount ?? DATA.records.length;
  const tokenCount = qa.token_count ?? qa.tokenCount ?? 0;
  const lemmaCount = qa.lemma_count ?? qa.lemmaCount ?? 0;
  const uncertainCount = qa.uncertain_record_count ?? qa.uncertainRecordCount ?? 0;
  const deletedCount = qa.deleted_or_omitted_record_count ?? qa.deletedRecordCount ?? 0;
  const cards = [
    statCard("Source lines", fmtStat(totalSourceLines)),
    statCard("Nonblank records", fmtStat(completedRecords)),
    statCard("Tokens", fmtStat(tokenCount)),
    statCard("Lemmas", fmtStat(lemmaCount)),
    statCard("Uncertain readings", fmtStat(uncertainCount), "uncertain"),
    statCard("Deleted / omitted", fmtStat(deletedCount), "deleted"),
  ];
  UI.statsGrid.replaceChildren(...cards);
}

function getFilteredRecords() {
  const terms = normalizeSearch(state.query).split(/\s+/).filter(Boolean);
  return DATA.records.filter((record) => {
    if (state.mode === "uncertain" && !record.isUncertain) return false;
    if (state.mode === "deleted" && !record.isDeleted) return false;
    if (state.mode === "emended" && !record.hasEmendation) return false;
    if (terms.length === 0) return true;
    return terms.every((term) => record.searchBlob.includes(term));
  });
}

function linePreview(record) {
  const text = record.isDeleted
    ? "OCR noise / omitted line"
    : (record.reading || record.src || "");
  return text.length > 140 ? `${text.slice(0, 140).trimEnd()}…` : text;
}

function statusLabel(record) {
  if (record.status === "deleted") return "deleted";
  if (record.status === "omitted") return "omitted";
  if (record.status === "uncertain") return "uncertain";
  return "analysis";
}

function renderIndex(filtered) {
  const fragment = document.createDocumentFragment();
  if (filtered.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No lines match the current search.";
    fragment.appendChild(empty);
  } else {
    for (const record of filtered) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "line-card";
      button.dataset.sl = String(record.sl);
      if (record.sl === state.selectedSl) button.classList.add("is-selected");

      const meta = document.createElement("div");
      meta.className = "line-meta";
      meta.innerHTML = `<span>Line ${record.sl}</span><span>${statusLabel(record)}</span>`;
      button.appendChild(meta);

      const snippet = document.createElement("div");
      snippet.className = "line-snippet";
      snippet.textContent = linePreview(record);
      button.appendChild(snippet);

      const badges = document.createElement("div");
      badges.className = "badges";
      if (record.isUncertain) badges.appendChild(badge("uncertain", "uncertain"));
      if (record.isDeleted) badges.appendChild(badge(record.status === "omitted" ? "omitted" : "deleted", "deleted"));
      if (record.hasEmendation) badges.appendChild(badge("emended", "emended"));
      button.appendChild(badges);

      button.addEventListener("click", () => {
        setSelected(record.sl, true);
      });

      fragment.appendChild(button);
    }
  }

  UI.lineIndex.replaceChildren(fragment);
  UI.sidebarTitle.textContent = state.mode === "all"
    ? "All lines"
    : state.mode === "uncertain"
      ? "Uncertain lines"
      : state.mode === "deleted"
        ? "Deleted / OCR noise"
        : "Emended lines";
  UI.sidebarCount.textContent = `${fmtStat(filtered.length)} shown of ${fmtStat(DATA.records.length)}`;
}

function syntaxValue(value) {
  if (value == null || value === "") return "";
  return String(value);
}

function renderTokens(record) {
  const table = document.createElement("table");
  table.className = "tokens-table";
  const thead = document.createElement("thead");
  thead.innerHTML = "<tr><th>#</th><th>Form</th><th>Lemma</th><th>POS</th><th>Morphology</th><th>Gloss</th></tr>";
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (const [index, tok] of (record.tok || []).entries()) {
    const tr = document.createElement("tr");
    const [form, lemma, pos, morph, gloss] = tok;
    tr.innerHTML = `
      <td class="mono">${index + 1}</td>
      <td>${escapeHtml(form)}</td>
      <td>${escapeHtml(lemma)}</td>
      <td>${escapeHtml(pos)}</td>
      <td>${escapeHtml(morph)}</td>
      <td>${escapeHtml(gloss)}</td>
    `;
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  return table;
}

function renderNotes(title, subtitle, notes, extraClass = "") {
  const section = document.createElement("section");
  section.className = `section-card ${extraClass}`.trim();
  const heading = document.createElement("h3");
  heading.innerHTML = `${escapeHtml(title)} <span>${escapeHtml(subtitle)}</span>`;
  section.appendChild(heading);

  const list = document.createElement("ul");
  list.className = "notes-list";
  for (const note of notes) {
    const item = document.createElement("li");
    item.textContent = note;
    list.appendChild(item);
  }
  section.appendChild(list);
  return section;
}

function renderDetail(record) {
  if (!record) {
    UI.detailPanel.innerHTML = `
      <div class="empty-state">
        <h2 class="detail-title">No record selected</h2>
        <p class="small-note">Try a search, or choose a line from the index.</p>
      </div>
    `;
    return;
  }

  const wrapper = document.createElement("article");

  const top = document.createElement("div");
  top.className = "detail-top";

  const headingWrap = document.createElement("div");
  const title = document.createElement("h2");
  title.className = "detail-title";
  title.textContent = `Line ${record.sl}`;
  const sub = document.createElement("p");
  sub.className = "detail-subtitle";
  sub.textContent = record.status === "deleted"
    ? "Deleted / OCR noise"
    : record.status === "omitted"
      ? "Omitted from continuous text"
      : record.status === "uncertain"
        ? "Uncertain reading"
        : "Corpus analysis";
  headingWrap.append(title, sub);

  const actions = document.createElement("div");
  actions.className = "detail-actions";
  const prev = document.createElement("button");
  prev.type = "button";
  prev.className = "nav-button";
  prev.textContent = "Previous";
  prev.disabled = !getNeighbor(record.sl, -1);
  prev.addEventListener("click", () => {
    const neighbor = getNeighbor(record.sl, -1);
    if (neighbor) setSelected(neighbor.sl, true);
  });
  const next = document.createElement("button");
  next.type = "button";
  next.className = "nav-button";
  next.textContent = "Next";
  next.disabled = !getNeighbor(record.sl, 1);
  next.addEventListener("click", () => {
    const neighbor = getNeighbor(record.sl, 1);
    if (neighbor) setSelected(neighbor.sl, true);
  });
  actions.append(prev, next);

  top.append(headingWrap, actions);
  wrapper.appendChild(top);

  const reading = document.createElement("section");
  reading.className = "reading-block";
  const label = document.createElement("p");
  label.className = "reading-label";
  label.textContent = "Reading";
  const readingText = document.createElement("p");
  readingText.className = "reading-text";
  readingText.textContent = record.reading;
  const source = document.createElement("div");
  source.className = "source-line";
  source.innerHTML = `<strong>Source:</strong> ${escapeHtml(record.src)}`;
  reading.append(label, readingText, source);

  if (record.ana && record.ana !== record.src) {
    const ana = document.createElement("div");
    ana.className = "source-line";
    ana.innerHTML = `<strong>Analyzed:</strong> ${escapeHtml(record.ana)}`;
    reading.appendChild(ana);
  }

  /* Audio player button — hooks into persistent audioState */
  const audioInfo = audioForLine(record.sl);
  if (audioInfo) {
    const audioBlock = document.createElement("div");
    audioBlock.className = "audio-block";
    const isThisSection = audioState.file === audioInfo.file;
    const showPause = isThisSection && audioState.playing;
    audioBlock.innerHTML = `
      <div class="audio-header">
        <button class="audio-play-btn${showPause ? " is-playing" : ""}" type="button" aria-label="Play audio">${showPause ? "&#9646;&#9646;" : "&#9654;"}</button>
        <span class="audio-label">Listen — lines ${audioInfo.start}–${audioInfo.end}</span>
      </div>
    `;
    const btn = audioBlock.querySelector(".audio-play-btn");

    btn.addEventListener("click", () => {
      toggleAudio(audioInfo);
    });

    reading.appendChild(audioBlock);
  }

  wrapper.appendChild(reading);

  const info = document.createElement("div");
  info.className = "info-grid";

  const literal = document.createElement("section");
  literal.className = "info-card";
  literal.innerHTML = `<h3>Literal translation</h3><p>${escapeHtml(record.lit || "")}</p>`;

  const smooth = document.createElement("section");
  smooth.className = "info-card";
  smooth.innerHTML = `<h3>Smooth translation</h3><p>${escapeHtml(record.sm || "")}</p>`;

  info.append(literal, smooth);
  wrapper.appendChild(info);

  if (record.unc.length) {
    wrapper.appendChild(
      renderNotes(
        "Uncertainty register",
        "flagged readings",
        record.unc,
        "uncertain-note"
      )
    );
  }

  if (record.emd) {
    wrapper.appendChild(
      renderNotes(
        "Emendation note",
        "editorial intervention",
        [record.emd],
        "uncertain-note"
      )
    );
  }

  const syntax = document.createElement("section");
  syntax.className = "section-card";
  const syntaxTitle = document.createElement("h3");
  syntaxTitle.innerHTML = `Syntax <span>structure notes</span>`;
  const syntaxGrid = document.createElement("div");
  syntaxGrid.className = "syntax-grid";
  const syn = record.syn || {};
  const order = ["mc", "sub", "svo", "ptc", "app", "rhet"];
  for (const key of order) {
    if (syn[key] == null || syn[key] === "") continue;
    const item = document.createElement("div");
    item.className = "syntax-item";
    const k = document.createElement("div");
    k.className = "syntax-key";
    k.textContent = key;
    const v = document.createElement("p");
    v.className = "syntax-value";
    v.textContent = syntaxValue(syn[key]);
    item.append(k, v);
    syntaxGrid.appendChild(item);
  }
  syntax.append(syntaxTitle, syntaxGrid);
  wrapper.appendChild(syntax);

  const tokens = document.createElement("section");
  tokens.className = "section-card";
  const tokensTitle = document.createElement("h3");
  tokensTitle.innerHTML = `Tokens <span>morphology</span>`;
  tokens.append(tokensTitle, renderTokens(record));
  wrapper.appendChild(tokens);

  UI.detailPanel.replaceChildren(wrapper);
}

function getNeighbor(sl, delta) {
  const filtered = getFilteredRecords();
  const index = filtered.findIndex((record) => record.sl === sl);
  if (index === -1) return null;
  return filtered[index + delta] || null;
}

function setMode(mode) {
  state.mode = mode;
  document.querySelectorAll(".filter-pill").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.mode === mode);
  });
  rerender();
}

function setSelected(sl, fromClick = false) {
  state.selectedSl = sl;
  const filtered = getFilteredRecords();
  const record = filtered.find((item) => item.sl === sl) || DATA.records.find((item) => item.sl === sl);
  renderIndex(filtered);
  renderDetail(record);
  if (fromClick) {
    location.hash = `line-${sl}`;
  }
  requestAnimationFrame(() => {
    const selected = UI.lineIndex.querySelector(`[data-sl="${sl}"]`);
    selected?.scrollIntoView({ block: "nearest" });
  });
}

function rerender() {
  const filtered = getFilteredRecords();
  renderIndex(filtered);
  if (!filtered.some((record) => record.sl === state.selectedSl)) {
    state.selectedSl = filtered[0]?.sl ?? null;
  }
  renderDetail(filtered.find((record) => record.sl === state.selectedSl) || null);
}

function bindEvents() {
  UI.searchInput.addEventListener("input", (event) => {
    state.query = event.target.value;
    rerender();
  });

  document.querySelectorAll(".filter-pill").forEach((button) => {
    button.addEventListener("click", () => setMode(button.dataset.mode));
  });

  UI.clearSelection.addEventListener("click", () => {
    state.query = "";
    state.mode = "all";
    UI.searchInput.value = "";
    document.querySelectorAll(".filter-pill").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.mode === "all");
    });
    rerender();
  });

  UI.jumpUncertain.addEventListener("click", () => {
    state.mode = "uncertain";
    document.querySelectorAll(".filter-pill").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.mode === "uncertain");
    });
    rerender();
    const first = getFilteredRecords()[0];
    if (first) setSelected(first.sl, true);
  });

  UI.jumpDeleted.addEventListener("click", () => {
    state.mode = "deleted";
    document.querySelectorAll(".filter-pill").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.mode === "deleted");
    });
    rerender();
    const first = getFilteredRecords()[0];
    if (first) setSelected(first.sl, true);
  });

  UI.statsGrid.addEventListener("click", (event) => {
    const button = event.target.closest("[data-jump]");
    if (!button) return;
    setMode(button.dataset.jump);
  });

  window.addEventListener("hashchange", () => {
    const match = location.hash.match(/line-(\d+)/);
    if (!match) return;
    const sl = Number(match[1]);
    const record = DATA.records.find((item) => item.sl === sl);
    if (record) setSelected(record.sl);
  });

  document.addEventListener("keydown", (event) => {
    if (
      event.target instanceof HTMLElement &&
      (event.target.tagName === "INPUT" || event.target.tagName === "TEXTAREA")
    ) {
      return;
    }
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    const delta = event.key === "ArrowDown" ? 1 : -1;
    const neighbor = getNeighbor(state.selectedSl, delta);
    if (!neighbor) return;
    event.preventDefault();
    setSelected(neighbor.sl, true);
  });
}

function init() {
  if (!DATA || !Array.isArray(DATA.records)) {
    document.body.innerHTML = "<main class='page-shell'><div class='detail-panel'><h1>Data missing</h1><p class='small-note'>window.PERI_PASCHA_DATA was not found. Load site/data.js before app.js.</p></div></main>";
    return;
  }

  DATA.records = DATA.records.map(enrichRecord).sort((a, b) => a.sl - b.sl);

  UI.statsGrid = document.getElementById("stats-grid");
  UI.searchInput = document.getElementById("search-input");
  UI.lineIndex = document.getElementById("line-index");
  UI.detailPanel = document.getElementById("detail-panel");
  UI.sidebarTitle = document.getElementById("sidebar-title");
  UI.sidebarCount = document.getElementById("sidebar-count");
  UI.jumpUncertain = document.getElementById("jump-uncertain");
  UI.jumpDeleted = document.getElementById("jump-deleted");
  UI.clearSelection = document.getElementById("clear-selection");

  renderStats();
  bindEvents();

  const hashMatch = location.hash.match(/line-(\d+)/);
  const initialSl = hashMatch ? Number(hashMatch[1]) : DATA.records[0]?.sl;
  state.selectedSl = initialSl ?? null;
  rerender();
}

document.addEventListener("DOMContentLoaded", init);
