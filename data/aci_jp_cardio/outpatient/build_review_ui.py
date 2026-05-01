#!/usr/bin/env python3
"""
Build a single-file HTML reviewer UI for the 22 outpatient cardio benchmark cases.

Usage:
    python3 build_review_ui.py

Output:
    review.html  (single file, opens in any browser, no server needed)
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent
CASES_DIR = ROOT / "cases"
OUT_HTML = ROOT / "review.html"

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ACI-JP-Cardio Outpatient — 症例レビュー</title>
<style>
  :root {
    --bg: #fafaf7;
    --panel: #ffffff;
    --text: #222;
    --muted: #6b7280;
    --border: #e5e7eb;
    --accent: #2563eb;
    --ok: #10b981;
    --warn: #f59e0b;
    --hold: #6b7280;
    --neg-ctrl: #c026d3;
    --typical: #0ea5e9;
    --atypical: #ef4444;
    --borderline: #a855f7;
    --scenario-a: #0891b2;
    --scenario-b: #ea580c;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Hiragino Kaku Gothic ProN", "Yu Gothic", sans-serif;
    background: var(--bg);
    color: var(--text);
    font-size: 14px;
    line-height: 1.6;
  }
  .layout {
    display: grid;
    grid-template-columns: 300px 1fr;
    grid-template-rows: 56px 1fr;
    height: 100vh;
  }
  header {
    grid-column: 1 / -1;
    display: flex;
    align-items: center;
    padding: 0 20px;
    background: var(--panel);
    border-bottom: 1px solid var(--border);
    gap: 16px;
  }
  header h1 { font-size: 16px; margin: 0; font-weight: 600; }
  header .meta { color: var(--muted); font-size: 13px; }
  header .actions { margin-left: auto; display: flex; gap: 8px; }
  header button {
    padding: 6px 12px;
    border: 1px solid var(--border);
    background: var(--panel);
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
  }
  header button:hover { background: #f3f4f6; }
  header button.primary { background: var(--accent); color: white; border-color: var(--accent); }

  aside {
    grid-row: 2;
    overflow-y: auto;
    background: var(--panel);
    border-right: 1px solid var(--border);
    padding: 8px 0;
  }
  aside .case-item {
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  aside .case-item:hover { background: #f9fafb; }
  aside .case-item.active { background: #eff6ff; border-left: 3px solid var(--accent); padding-left: 11px; }
  aside .case-item .id { font-weight: 600; font-size: 13px; display: flex; align-items: center; gap: 6px; }
  aside .case-item .desc { color: var(--muted); font-size: 12px; line-height: 1.4; }
  aside .case-item .badges { display: flex; gap: 4px; margin-top: 2px; flex-wrap: wrap; }
  .badge {
    font-size: 10px;
    padding: 1px 6px;
    border-radius: 4px;
    font-weight: 500;
  }
  .badge.A { background: #cffafe; color: #155e75; }
  .badge.B { background: #ffedd5; color: #9a3412; }
  .badge.typical { background: #e0f2fe; color: #075985; }
  .badge.atypical { background: #fef3c7; color: #92400e; }
  .badge.borderline { background: #f3e8ff; color: #7e22ce; }
  .badge.neg-ctrl { background: #fae8ff; color: #86198f; }
  .badge.status-ok { background: #d1fae5; color: #065f46; }
  .badge.status-warn { background: #fef3c7; color: #92400e; }
  .badge.status-hold { background: #e5e7eb; color: #374151; }

  main {
    grid-row: 2;
    overflow-y: auto;
    padding: 20px 28px 60px 28px;
  }

  .case-header {
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 2px solid var(--border);
  }
  .case-header .id-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .case-header h2 { font-size: 18px; margin: 0; }
  .case-header .desc { color: var(--muted); margin-top: 4px; font-size: 13px; }

  .scenario-banner {
    padding: 8px 14px;
    border-radius: 6px;
    margin-bottom: 14px;
    font-size: 13px;
    font-weight: 500;
  }
  .scenario-banner.A { background: #ecfeff; border-left: 4px solid var(--scenario-a); color: #0e7490; }
  .scenario-banner.B { background: #fff7ed; border-left: 4px solid var(--scenario-b); color: #c2410c; }

  .patient-summary {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 6px 16px;
    background: #f9fafb;
    padding: 12px 16px;
    border-radius: 6px;
    margin-bottom: 14px;
    font-size: 13px;
  }
  .patient-summary dt { color: var(--muted); font-weight: 500; }
  .patient-summary dd { margin: 0; word-break: break-word; }

  .reception-vitals {
    background: #f0f9ff;
    border: 1px solid #bae6fd;
    padding: 10px 14px;
    border-radius: 6px;
    margin-bottom: 14px;
    font-size: 13px;
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
  }
  .reception-vitals .label { font-weight: 600; color: #0369a1; }
  .reception-vitals .item { color: #075985; }

  .pair {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    margin-bottom: 16px;
  }
  @media (max-width: 1100px) {
    .pair { grid-template-columns: 1fr; }
  }

  .panel {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px 16px;
  }
  .panel h3 {
    margin: 0 0 8px 0;
    font-size: 13px;
    font-weight: 600;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.4px;
  }
  .panel .section { margin-bottom: 10px; }
  .panel .section:last-child { margin-bottom: 0; }
  .panel .section-label {
    font-size: 11px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.3px;
    margin-bottom: 2px;
  }
  .panel .body {
    white-space: pre-wrap;
    font-size: 13px;
    color: var(--text);
  }
  .panel .body.dialogue {
    background: #fff7ed;
    padding: 10px;
    border-left: 3px solid var(--scenario-b);
    border-radius: 0 4px 4px 0;
    line-height: 1.8;
  }
  .panel .body.physician {
    background: #ecfeff;
    padding: 10px;
    border-left: 3px solid var(--scenario-a);
    border-radius: 0 4px 4px 0;
  }
  .panel .body.empty { color: var(--muted); font-style: italic; }

  .triage-banner {
    background: #ecfdf5;
    border: 2px solid var(--ok);
    padding: 10px 14px;
    border-radius: 8px;
    margin-bottom: 14px;
    font-size: 14px;
  }
  .triage-banner .label { font-weight: 700; color: #047857; margin-right: 8px; }
  .triage-banner .value { color: #064e3b; font-weight: 600; }
  .triage-banner.urgent { background: #fef2f2; border-color: #ef4444; }
  .triage-banner.urgent .label { color: #b91c1c; }
  .triage-banner.urgent .value { color: #7f1d1d; }

  .key-facts {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 14px;
    font-size: 13px;
  }
  .key-facts h3 { margin-top: 0; font-size: 13px; color: #047857; }
  .key-facts dl { display: grid; grid-template-columns: max-content 1fr; gap: 4px 12px; margin: 0; }
  .key-facts dt { color: #065f46; font-weight: 500; }
  .key-facts dd { margin: 0; word-break: break-word; }
  .key-facts .chips { display: flex; flex-wrap: wrap; gap: 4px; }
  .key-facts .chip {
    background: white;
    border: 1px solid #86efac;
    color: #065f46;
    padding: 1px 8px;
    border-radius: 12px;
    font-size: 12px;
  }
  .key-facts .chip.must-not-miss {
    background: #fef2f2;
    border-color: #fca5a5;
    color: #991b1b;
    font-weight: 600;
  }

  .rag-citations {
    background: #fef9c3;
    border: 1px solid #fde047;
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 14px;
    font-size: 13px;
  }
  .rag-citations h3 { margin-top: 0; font-size: 13px; color: #854d0e; }
  .rag-citations ul { margin: 0; padding-left: 20px; }

  .notes-reviewer {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 14px;
    font-size: 13px;
  }
  .notes-reviewer h3 { margin-top: 0; font-size: 13px; color: #1e40af; }

  .annotation-panel {
    background: var(--panel);
    border: 2px solid var(--accent);
    border-radius: 8px;
    padding: 14px 16px;
    position: sticky;
    bottom: 14px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  }
  .annotation-panel h3 { margin-top: 0; font-size: 13px; color: var(--accent); }
  .annotation-panel .verdict {
    display: flex;
    gap: 8px;
    margin-bottom: 10px;
  }
  .annotation-panel .verdict button {
    flex: 1;
    padding: 8px 12px;
    border: 1px solid var(--border);
    background: white;
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
  }
  .annotation-panel .verdict button.selected.ok { background: var(--ok); color: white; border-color: var(--ok); }
  .annotation-panel .verdict button.selected.warn { background: var(--warn); color: white; border-color: var(--warn); }
  .annotation-panel .verdict button.selected.hold { background: var(--hold); color: white; border-color: var(--hold); }
  .annotation-panel textarea {
    width: 100%;
    min-height: 60px;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 8px 10px;
    font-family: inherit;
    font-size: 13px;
    resize: vertical;
  }
  .annotation-panel .saved-indicator { color: var(--ok); font-size: 12px; margin-top: 4px; }
  .keyboard-hint { color: var(--muted); font-size: 11px; margin-top: 6px; }
  kbd {
    background: #f3f4f6;
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 1px 5px;
    font-family: monospace;
    font-size: 11px;
  }
</style>
</head>
<body>
<div class="layout">
  <header>
    <h1>ACI-JP-Cardio Outpatient レビュー</h1>
    <span class="meta" id="case-counter"></span>
    <div class="actions">
      <button id="prev-btn">← 前 <kbd>k</kbd></button>
      <button id="next-btn">次 <kbd>j</kbd> →</button>
      <button id="export-btn" class="primary">注釈をエクスポート</button>
    </div>
  </header>

  <aside id="sidebar"></aside>
  <main id="main">
    <div class="empty">症例を選択してください</div>
  </main>
</div>

<script>
const CASES = __CASES_JSON__;

let currentIdx = 0;
const STORAGE_KEY = "aci_jp_outpatient_annotations_v1";

function loadAnnotations() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"); }
  catch { return {}; }
}
function saveAnnotations(annotations) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(annotations));
}

function escapeHtml(s) {
  if (!s) return "";
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function isUrgentTriage(triage) {
  if (!triage) return false;
  return /緊急|入院/.test(triage);
}

function renderSidebar() {
  const sb = document.getElementById("sidebar");
  const annotations = loadAnnotations();
  sb.innerHTML = "";
  CASES.forEach((c, idx) => {
    const a = annotations[c.encounter_id] || {};
    const item = document.createElement("div");
    item.className = "case-item" + (idx === currentIdx ? " active" : "");
    item.onclick = () => { currentIdx = idx; render(); };

    const sceBadge = c.scenario === "shoshin_walkin"
      ? '<span class="badge B">B 初診</span>'
      : '<span class="badge A">A 再診/紹介</span>';
    const diffBadge = c.is_negative_control
      ? '<span class="badge neg-ctrl">陰性対照</span>'
      : `<span class="badge ${c.difficulty}">${c.difficulty}</span>`;
    const verdictBadge = a.verdict
      ? `<span class="badge status-${a.verdict === "ok" ? "ok" : a.verdict === "warn" ? "warn" : "hold"}">${
          a.verdict === "ok" ? "OK" : a.verdict === "warn" ? "要修正" : "保留"
        }</span>` : "";

    item.innerHTML = `
      <div class="id">${sceBadge} ${c.encounter_id}</div>
      <div class="desc">${escapeHtml(c.disease_label_jp)}</div>
      <div class="badges">${diffBadge}${verdictBadge}</div>
    `;
    sb.appendChild(item);
  });
}

function render() {
  renderSidebar();
  const c = CASES[currentIdx];
  if (!c) return;
  const main = document.getElementById("main");
  document.getElementById("case-counter").textContent = `${currentIdx + 1} / ${CASES.length}`;

  const a = loadAnnotations()[c.encounter_id] || {};
  const isB = c.scenario === "shoshin_walkin";

  const p = c.patient || {};
  const e = c.encounter || {};
  const rv = c.reception_vitals || {};
  const kf = c.key_facts || {};

  // Patient summary
  const patientHtml = `
    <dl class="patient-summary">
      <dt>患者</dt><dd>${p.age}歳 ${escapeHtml(p.gender)}・血液型 ${escapeHtml(p.blood_type || "?")}</dd>
      <dt>主訴</dt><dd>${escapeHtml(e.chief_complaint || "")}${
        e.secondary_complaints && e.secondary_complaints.length
          ? "（副: " + e.secondary_complaints.map(escapeHtml).join("、") + "）" : ""
      }</dd>
      <dt>既往</dt><dd>${(p.comorbidities || []).map(escapeHtml).join("、") || "—"}</dd>
      <dt>持参薬</dt><dd>${(p.current_medications || []).map(escapeHtml).join("、") || "—"}</dd>
      <dt>アレルギー</dt><dd>${(p.allergies || []).map(escapeHtml).join("、") || "—"}</dd>
      <dt>家族歴</dt><dd>${(p.family_history || []).map(escapeHtml).join("、") || "—"}</dd>
      <dt>社会歴</dt><dd>${escapeHtml(p.social_history || "—")}</dd>
      <dt>受診</dt><dd>${escapeHtml(e.encounter_date || "")}・${escapeHtml(e.department || "")}・${escapeHtml(e.type || "")}</dd>
    </dl>
  `;

  // Reception vitals
  const rvHtml = Object.keys(rv).length ? `
    <div class="reception-vitals">
      <span class="label">受付バイタル:</span>
      ${rv.BP_sys != null ? `<span class="item">BP ${rv.BP_sys}/${rv.BP_dia} mmHg</span>` : ""}
      ${rv.HR != null ? `<span class="item">HR ${rv.HR}/min</span>` : ""}
      ${rv.SpO2 != null ? `<span class="item">SpO2 ${rv.SpO2}%</span>` : ""}
      ${rv.RR != null ? `<span class="item">RR ${rv.RR}</span>` : ""}
      ${rv.BT != null ? `<span class="item">BT ${rv.BT}℃</span>` : ""}
    </div>
  ` : "";

  // Triage banner (must show top!)
  const triageStr = kf.expected_triage || "—";
  const altTriage = (kf.alternative_acceptable_triage && kf.alternative_acceptable_triage.length)
    ? ` <span style="color:var(--muted); font-size:12px;">(代替: ${kf.alternative_acceptable_triage.map(escapeHtml).join(", ")})</span>` : "";
  const triageHtml = `
    <div class="triage-banner ${isUrgentTriage(triageStr) ? "urgent" : ""}">
      <span class="label">期待される triage 判断:</span>
      <span class="value">${escapeHtml(triageStr)}</span>${altTriage}
    </div>
  `;

  // Input panel
  let inputBody = "";
  if (isB) {
    inputBody = `
      <div class="section">
        <div class="section-label">口語対話 (Pattern B)</div>
        <div class="body dialogue">${escapeHtml(c.input_pattern_B || "")}</div>
      </div>
    `;
  } else {
    const ipa = c.input_pattern_A || {};
    const ps = ipa.physician_summary || {};
    const sections = [
      ["医師サマリ (raw_text)", ps.raw_text],
      ["お薬手帳", ps.medication_list],
      ["診察所見", ps.exam_findings],
      ["検査結果", ps.lab_results],
    ];
    inputBody = sections.map(([label, body]) => `
      <div class="section">
        <div class="section-label">${escapeHtml(label)}</div>
        <div class="body physician${body ? "" : " empty"}">${body ? escapeHtml(body) : "（記載なし）"}</div>
      </div>
    `).join("");
  }

  // Reference SOAP
  const soap = c.reference_soap || {};
  const soapBody = ["S", "O", "A", "P"].map(sec => `
    <div class="section">
      <div class="section-label">${sec}</div>
      <div class="body${soap[sec] ? "" : " empty"}">${soap[sec] ? escapeHtml(soap[sec]) : "（記載なし）"}</div>
    </div>
  `).join("");

  const adm = c.reference_admission_summary;
  const admBody = adm ? `
    <div class="section">
      <div class="section-label">入院時サマリ</div>
      <div class="body">${escapeHtml(adm)}</div>
    </div>
  ` : "";

  // key_facts
  const triageInfoHtml = `
    ${kf.expected_triage ? `<dt>期待 triage</dt><dd><strong>${escapeHtml(kf.expected_triage)}</strong></dd>` : ""}
    ${kf.alternative_acceptable_triage && kf.alternative_acceptable_triage.length ? `<dt>代替 triage</dt><dd>${kf.alternative_acceptable_triage.map(escapeHtml).join("、")}</dd>` : ""}
    ${kf.differential_diagnoses && kf.differential_diagnoses.length ? `<dt>鑑別診断</dt><dd><div class="chips">${kf.differential_diagnoses.map(d => `<span class="chip">${escapeHtml(d)}</span>`).join("")}</div></dd>` : ""}
    ${kf.must_not_miss && kf.must_not_miss.length ? `<dt>Must-not-miss</dt><dd><div class="chips">${kf.must_not_miss.map(d => `<span class="chip must-not-miss">${escapeHtml(d)}</span>`).join("")}</div></dd>` : ""}
    ${kf.appropriate_next_tests && kf.appropriate_next_tests.length ? `<dt>推奨検査</dt><dd><div class="chips">${kf.appropriate_next_tests.map(d => `<span class="chip">${escapeHtml(d)}</span>`).join("")}</div></dd>` : ""}
  `;

  const kfHtml = `
    <div class="key-facts">
      <h3>key_facts (eval runner が triage / 鑑別 / must_not_miss F1 を計算する正解集合)</h3>
      <dl>
        ${triageInfoHtml}
        ${kf.diagnoses && kf.diagnoses.length ? `<dt>診断 (確定)</dt><dd><div class="chips">${kf.diagnoses.map(d => `<span class="chip">${escapeHtml(d)}</span>`).join("")}</div></dd>` : ""}
        ${kf.diagnoses_provisional && kf.diagnoses_provisional.length ? `<dt>暫定診断</dt><dd><div class="chips">${kf.diagnoses_provisional.map(d => `<span class="chip">${escapeHtml(d)}</span>`).join("")}</div></dd>` : ""}
        ${kf.medications_to_start && kf.medications_to_start.length ? `<dt>開始薬</dt><dd><div class="chips">${kf.medications_to_start.map(d => `<span class="chip">${escapeHtml(d)}</span>`).join("")}</div></dd>` : ""}
        ${kf.medications_to_continue && kf.medications_to_continue.length ? `<dt>継続薬</dt><dd><div class="chips">${kf.medications_to_continue.map(d => `<span class="chip">${escapeHtml(d)}</span>`).join("")}</div></dd>` : ""}
        ${kf.medications_to_stop && kf.medications_to_stop.length ? `<dt>中止薬</dt><dd><div class="chips">${kf.medications_to_stop.map(d => `<span class="chip">${escapeHtml(d)}</span>`).join("")}</div></dd>` : ""}
        ${kf.medications_to_consider && kf.medications_to_consider.length ? `<dt>導入検討</dt><dd><div class="chips">${kf.medications_to_consider.map(d => `<span class="chip">${escapeHtml(d)}</span>`).join("")}</div></dd>` : ""}
        ${kf.labs ? `<dt>検査値</dt><dd>${Object.entries(kf.labs).map(([k, v]) => `${k}: ${v}`).join(", ")}</dd>` : ""}
        ${kf.scores ? `<dt>スコア</dt><dd>${Object.entries(kf.scores).map(([k, v]) => `${k}: ${v}`).join(", ")}</dd>` : ""}
        ${kf.disposition ? `<dt>転帰</dt><dd>${escapeHtml(kf.disposition)}</dd>` : ""}
      </dl>
    </div>
  `;

  // RAG citations
  const ragHtml = c.rag_citations && c.rag_citations.length ? `
    <div class="rag-citations">
      <h3>参照ガイドライン (rag_citations)</h3>
      <ul>
        ${c.rag_citations.map(r => `<li><strong>${escapeHtml(r.guideline)}</strong> — ${escapeHtml(r.section)}: ${escapeHtml(r.key_point)}</li>`).join("")}
      </ul>
    </div>
  ` : "";

  const reviewerNotesHtml = c.notes_for_reviewer ? `
    <div class="notes-reviewer">
      <h3>レビュー時の評価ポイント (notes_for_reviewer)</h3>
      <div>${escapeHtml(c.notes_for_reviewer)}</div>
    </div>
  ` : "";

  const verdictHtml = `
    <div class="annotation-panel">
      <h3>レビュー判定 (${c.encounter_id})</h3>
      <div class="verdict">
        <button data-v="ok" class="${a.verdict === "ok" ? "selected ok" : ""}">✓ OK <kbd>1</kbd></button>
        <button data-v="warn" class="${a.verdict === "warn" ? "selected warn" : ""}">⚠ 要修正 <kbd>2</kbd></button>
        <button data-v="hold" class="${a.verdict === "hold" ? "selected hold" : ""}">? 保留 <kbd>3</kbd></button>
      </div>
      <textarea id="comment-area" placeholder="コメント・修正指示を記載 (自動保存)">${escapeHtml(a.comment || "")}</textarea>
      <div class="saved-indicator" id="saved-indicator">${a.timestamp ? "最終保存: " + new Date(a.timestamp).toLocaleString("ja-JP") : ""}</div>
      <div class="keyboard-hint">キーボード: <kbd>j</kbd> 次 / <kbd>k</kbd> 前 / <kbd>1</kbd> OK / <kbd>2</kbd> 要修正 / <kbd>3</kbd> 保留</div>
    </div>
  `;

  const scenarioBanner = isB
    ? '<div class="scenario-banner B">📋 シナリオ B: 初診 walk-in — 診察前段階、受付バイタルのみ取得済</div>'
    : '<div class="scenario-banner A">📋 シナリオ A: 紹介状/再診 — 医師診察済、検査値・身体所見あり</div>';

  main.innerHTML = `
    <div class="case-header">
      <div class="id-row">
        <h2>${c.encounter_id}</h2>
        ${isB ? '<span class="badge B">初診 walk-in</span>' : '<span class="badge A">再診/紹介状</span>'}
        ${c.is_negative_control ? '<span class="badge neg-ctrl">陰性対照</span>' : `<span class="badge ${c.difficulty}">${c.difficulty}</span>`}
      </div>
      <div class="desc">${escapeHtml(c.disease_label_jp)}</div>
    </div>

    ${scenarioBanner}
    ${triageHtml}
    ${patientHtml}
    ${rvHtml}

    <div class="pair">
      <div class="panel">
        <h3>入力 (SLM への問診)</h3>
        ${inputBody}
      </div>
      <div class="panel">
        <h3>正解 reference SOAP</h3>
        ${soapBody}
        ${admBody}
      </div>
    </div>

    ${kfHtml}
    ${ragHtml}
    ${reviewerNotesHtml}
    ${verdictHtml}
  `;

  document.querySelectorAll(".verdict button").forEach(btn => {
    btn.onclick = () => setVerdict(btn.dataset.v);
  });
  const ta = document.getElementById("comment-area");
  if (ta) {
    let saveTimer;
    ta.oninput = () => {
      clearTimeout(saveTimer);
      saveTimer = setTimeout(() => updateAnnotation({ comment: ta.value }), 600);
    };
  }
}

function setVerdict(v) { updateAnnotation({ verdict: v }); }
function updateAnnotation(patch) {
  const c = CASES[currentIdx];
  const annotations = loadAnnotations();
  const cur = annotations[c.encounter_id] || {};
  annotations[c.encounter_id] = { ...cur, ...patch, timestamp: Date.now() };
  saveAnnotations(annotations);
  render();
}

function nextCase() { if (currentIdx < CASES.length - 1) { currentIdx++; render(); } }
function prevCase() { if (currentIdx > 0) { currentIdx--; render(); } }

document.addEventListener("keydown", e => {
  if (e.target.tagName === "TEXTAREA" || e.target.tagName === "INPUT") return;
  if (e.key === "j" || e.key === "ArrowDown") { e.preventDefault(); nextCase(); }
  else if (e.key === "k" || e.key === "ArrowUp") { e.preventDefault(); prevCase(); }
  else if (e.key === "1") setVerdict("ok");
  else if (e.key === "2") setVerdict("warn");
  else if (e.key === "3") setVerdict("hold");
});

document.getElementById("next-btn").onclick = nextCase;
document.getElementById("prev-btn").onclick = prevCase;
document.getElementById("export-btn").onclick = () => {
  const annotations = loadAnnotations();
  const blob = new Blob([JSON.stringify(annotations, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "aci_jp_outpatient_annotations_" + new Date().toISOString().slice(0, 10) + ".json";
  a.click();
  URL.revokeObjectURL(url);
};

render();
</script>
</body>
</html>
"""


def main():
    case_files = sorted(CASES_DIR.glob("JC-*.json"))
    cases = []
    for f in case_files:
        with open(f, encoding="utf-8") as fp:
            cases.append(json.load(fp))

    cases_json_str = json.dumps(cases, ensure_ascii=False)
    html = HTML_TEMPLATE.replace("__CASES_JSON__", cases_json_str)

    with open(OUT_HTML, "w", encoding="utf-8") as fp:
        fp.write(html)

    size_kb = OUT_HTML.stat().st_size / 1024
    print(f"wrote {OUT_HTML} ({size_kb:.1f} KB, {len(cases)} cases embedded)")


if __name__ == "__main__":
    main()
