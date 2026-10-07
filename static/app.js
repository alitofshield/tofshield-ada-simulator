"use strict";
let acquisitionLocked = false;
let appliedInstrument = null;
let instrumentFields = [];
let transformMode = 'dft';
let detectionStudyInput = null;
let detectionStudyResult = null;
const instrumentGroupDefinitions = {
  'Sampling inlet': 'Defines how the sample is transported from the environment or sampling point into the ionization region.',
  'Reagent-ion source': 'Describes the available reagent-ion signal used to support chemical ionization in a generated Vocus scenario.',
  'Reaction chamber': 'Records the illustrative conditions under which reagent ions and sample molecules interact before mass analysis.',
  'Ion transfer & vacuum': 'Describes transfer efficiency and the low-pressure environment that guides ions toward the TOF analyzer.',
  'TOF analyzer': 'Defines the displayed mass range and an additional educational broadening kernel expressed as resolving power.',
  'Detector & acquisition': 'Controls illustrative collection time, electronic response, background, noise and saturation behavior.',
  'Calibration & instrument state': 'Represents a controlled mass-axis offset for demonstrating calibration drift and review.'
};
const instrumentFieldDefinitions = {
  flow_ml_min: 'Volumetric sample flow entering the inlet. Together with inlet volume, it determines the illustrative transport delay.',
  volume_ml: 'Internal volume of the sample path used to estimate how long the sample takes to reach the response region.',
  inlet_temperature_c: 'Recorded inlet temperature context. No compound-specific heating, adsorption or decomposition law is applied.',
  dilution: 'Ratio by which the incoming sample is illustratively diluted before analysis; larger values reduce displayed response.',
  loss_percent: 'Illustrative fraction of signal removed by inlet-wall loss or transmission inefficiency.',
  carryover: 'Fixed residual signal added to represent material remaining from an earlier sample.',
  elapsed_s: 'Time elapsed since the sample reached the inlet; used by the response-time model.',
  response_s: 'Time constant controlling how quickly the illustrative signal approaches its steady response.',
  reagent_signal: 'Relative reagent-ion abundance compared with the reference condition; scales generated-response intensity.',
  pressure_mbar: 'Reaction-region pressure recorded as engineering context. The current model does not calculate pressure-dependent chemistry.',
  temperature_c: 'Reaction-region temperature recorded as context; no temperature-dependent kinetic model is claimed.',
  reaction_ms: 'Nominal residence or reaction time recorded for discussion; it does not calculate reaction kinetics.',
  field_td: 'Reduced electric field E/N in Townsend, relevant to PTR-style ion chemistry; stored here as context only.',
  humidity_percent: 'Relative humidity context for discussing water clustering and ion chemistry; no humidity law is applied.',
  response_factor: 'User-controlled empirical multiplier for educational sensitivity comparisons, not a calibrated response factor.',
  vacuum_mbar: 'Analyzer pressure context used to describe the vacuum state; it does not calculate collision probability.',
  transmission_percent: 'Illustrative percentage of ions transferred from the reaction region to the analyzer.',
  mass_rolloff: 'Optional exponential decrease in transmission as m/z increases, expressed per 100 Th.',
  mass_min: 'Lower mass-to-charge boundary retained in the configured display and analysis.',
  mass_max: 'Upper mass-to-charge boundary retained in the configured display and analysis.',
  resolving_power: 'Additional educational Gaussian broadening expressed as m/Δm at FWHM; it does not recover native resolution.',
  integration_s: 'Illustrative acquisition duration relative to a one-second reference; longer time scales accumulated signal.',
  gain: 'Dimensionless detector/electronics multiplier applied to the displayed response.',
  background: 'Constant baseline signal added across the configured mass range.',
  noise: 'Standard deviation of deterministic demonstration noise added to the displayed signal.',
  saturation: 'Maximum displayed intensity after gain, background and noise are applied.',
  drift_ppm: 'Uniform parts-per-million shift applied to the mass axis for calibration-drift demonstrations.'
};
function instrumentSettings() {
  if (acquisitionLocked) throw new Error("Imported acquisition settings are read-only. Start a new simulation to edit settings.");
  const form = document.querySelector('#instrument-form');
  if (!form.reportValidity()) throw new Error('Correct the instrument configuration values.');
  const values = Object.fromEntries(instrumentFields.map((f) => [f[1], Number(document.querySelector(`#instrument-${f[1]}`).value)]));
  values.reagent = document.querySelector('#configuration-reagent').value;
  values.state = document.querySelector('#configuration-state').value;
  if (values.mass_min >= values.mass_max) throw new Error('Minimum m/z must be below maximum m/z.');
  return values;
}
function setupInstrument(fields) {
  instrumentFields = fields;
  const groups = [...new Set(fields.map(f => f[0]))];
  document.querySelector('#instrument-fields').innerHTML = groups.map((group,index) => `<details class="configuration-group" data-instrument-group="${escapeHtml(group)}" open><summary><span>${String(index+1).padStart(2,'0')}</span><div><strong>${escapeHtml(group)}</strong><small>${escapeHtml(instrumentGroupDefinitions[group] || '')}</small></div></summary><div class="configuration-grid">${fields.filter(f=>f[0]===group).map(f=>`<label class="configuration-field"><span class="field-name">${escapeHtml(f[2])}</span><span class="field-definition">${escapeHtml(instrumentFieldDefinitions[f[1]] || '')}</span><input id="instrument-${f[1]}" type="number" step="any" min="${f[4]}" max="${f[5]}" value="${f[3]}" required /><span class="field-meta"><b>${f[6] ? 'MODELLED EFFECT' : 'CONTEXT ONLY'}</b> Default ${escapeHtml(f[3])} · Allowed ${escapeHtml(f[4])} to ${escapeHtml(f[5])}</span></label>`).join('')}</div></details>`).join('');
  const dirty = document.querySelector('#configuration-dirty');
  document.querySelector('#instrument-form').addEventListener('input',()=> dirty.textContent='Changes pending. Apply to refresh analysis; generate again to change reagent chemistry.');
  document.querySelector('#configuration-reagent').addEventListener('change',()=>els.vocusReagent.value=document.querySelector('#configuration-reagent').value);
  els.vocusReagent.addEventListener('change',()=>document.querySelector('#configuration-reagent').value=els.vocusReagent.value);
  document.querySelector('#instrument-form').addEventListener('submit',async event=>{
    event.preventDefault();
    try {
      const next = instrumentSettings();
      appliedInstrument = document.querySelector('#configuration-enabled').checked ? next : null;
      dirty.textContent='Configuration applied.';
      els.rangeMin.value=''; els.rangeMax.value='';
      if (state.fileId) await loadSpectrum({preserveFullRange:false});
    } catch(error) { toast(error.message,'error'); }
  });
  document.querySelector('#configuration-reset').addEventListener('click',async()=>{
    if(acquisitionLocked)return;
    fields.forEach(f=>document.querySelector(`#instrument-${f[1]}`).value=f[3]);
    document.querySelector('#configuration-reagent').value='I-'; els.vocusReagent.value='I-';
    document.querySelector('#configuration-state').value='ready';
    document.querySelector('#configuration-enabled').checked=false; appliedInstrument=null;
    dirty.textContent='Defaults restored; model off.';
    if(state.fileId) await loadSpectrum({preserveFullRange:false});
  });
  document.querySelector('#configuration-export').addEventListener('click',()=>{
    try {
      const blob=new Blob([JSON.stringify({version:'0.4.6',notice:'Illustrative demo inputs, not manufacturer specifications',enabled:document.querySelector('#configuration-enabled').checked,configuration:instrumentSettings()},null,2)],{type:'application/json'});
      const url=URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url;a.download='ADA-Instrument-Configuration.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    } catch(error) {toast(error.message,'error');}
  });
}

function setupWorkspaceTabs() {
  const tabs = [...document.querySelectorAll('[data-workspace-target]')];
  tabs.forEach(tab => tab.addEventListener('click', () => {
    const target = tab.dataset.workspaceTarget;
    tabs.forEach(item => item.classList.toggle('active', item === tab));
    document.querySelectorAll('.workspace-panel').forEach(panel => panel.classList.toggle('active', panel.id === target));
    window.scrollTo({top: 0, behavior: 'smooth'});
  }));
}

function parseNumberLines(value, paired = false) {
  return value.split(/\r?\n/).map(line => line.trim()).filter(Boolean).map((line, index) => {
    if (!paired) {
      const number = Number(line);
      if (!Number.isFinite(number)) throw new Error(`Blank response line ${index + 1} is not numeric.`);
      return number;
    }
    const parts = line.split(/[\s,;\t]+/).filter(Boolean).map(Number);
    if (parts.length !== 2 || !parts.every(Number.isFinite)) throw new Error(`Calibration line ${index + 1} must contain concentration,response.`);
    return {concentration: parts[0], response: parts[1]};
  });
}

function detectionPayload() {
  const method = document.querySelector('#detection-method').value;
  const payload = {
    analyte: document.querySelector('#detection-analyte').value.trim(),
    formula: document.querySelector('#detection-formula').value.trim(),
    quantifier_mz: Number(document.querySelector('#detection-mz').value),
    mz_tolerance: Number(document.querySelector('#detection-tolerance').value),
    concentration_unit: document.querySelector('#detection-unit').value.trim(),
    matrix: document.querySelector('#detection-matrix').value.trim(),
    method,
    validation_status: document.querySelector('#detection-validation').value,
  };
  if (method === 'user_supplied') {
    payload.lod = Number(document.querySelector('#detection-lod').value);
    payload.loq = Number(document.querySelector('#detection-loq').value);
  } else {
    payload.calibration = parseNumberLines(document.querySelector('#detection-calibration').value, true);
    payload.blanks = parseNumberLines(document.querySelector('#detection-blanks').value);
  }
  return payload;
}

function renderDetectionResult(result) {
  const unit = escapeHtml(result.concentration_unit);
  const r2 = result.r_squared == null ? '—' : formatNumber(result.r_squared, 6);
  document.querySelector('#detection-result').innerHTML = `<div><span>Analyte</span><strong>${escapeHtml(result.analyte)}${result.formula ? ` · ${escapeHtml(result.formula)}` : ''}</strong></div><div><span>LOD</span><strong>${escapeHtml(formatNumber(result.lod, 6))} ${unit}</strong></div><div><span>LOQ</span><strong>${escapeHtml(formatNumber(result.loq, 6))} ${unit}</strong></div><div><span>Calibration R²</span><strong>${escapeHtml(r2)}</strong></div><div><span>Method</span><strong>${escapeHtml(result.method_label)}</strong></div><div><span>Status</span><strong>${escapeHtml(result.validation_status)}</strong></div><p>${escapeHtml(result.limitations)}</p>`;
  document.querySelector('#detection-export').disabled = false;
}

function setupDetectionCapability() {
  const method = document.querySelector('#detection-method');
  const toggle = () => {
    const supplied = method.value === 'user_supplied';
    document.querySelector('#calibration-inputs').classList.toggle('hidden', supplied);
    document.querySelector('#supplied-limit-inputs').classList.toggle('hidden', !supplied);
  };
  method.addEventListener('change', toggle); toggle();
  document.querySelector('#detection-form').addEventListener('submit', async event => {
    event.preventDefault();
    try {
      const payload = detectionPayload();
      const result = await fetchJson('/api/detection-capability', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
      detectionStudyInput = payload; detectionStudyResult = result;
      renderDetectionResult(result);
      if (state.fileId) await loadSpectrum({preserveFullRange:true});
      toast('LOD/LOQ study calculated and applied.');
    } catch (error) { toast(error.message, 'error'); }
  });
  document.querySelector('#detection-clear').addEventListener('click', async () => {
    resetDetectionStudy();
    if (state.fileId) await loadSpectrum({preserveFullRange:true});
  });
  document.querySelector('#detection-export').addEventListener('click', () => {
    if (!detectionStudyResult) return;
    const blob = new Blob([JSON.stringify({viewer_version:'0.4.6', inputs:detectionStudyInput, results:detectionStudyResult}, null, 2)], {type:'application/json'});
    const url=URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download='ADA-LOD-LOQ-Study.json'; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
}


const state = {
  config: null,
  fileId: null,
  manifest: null,
  spectrum: null,
  candidateId: null,
  fullRange: null,
  datasetQuery: "",
  timeSeries: null,
  hdfMatches: [],
  hdfMatchIndex: -1,
};

const els = {
  activeFileTitle: document.querySelector("#active-file-title"),
  fileInput: document.querySelector("#file-input"),
  dropZone: document.querySelector("#drop-zone"),
  pathForm: document.querySelector("#path-form"),
  pathInput: document.querySelector("#path-input"),
  pathHelp: document.querySelector("#path-help"),
  fixtureButton: document.querySelector("#fixture-button"),
  vocusForm: document.querySelector("#vocus-panel"),
  vocusReagent: document.querySelector("#vocus-reagent"),
  vocusTargets: document.querySelector("#vocus-targets"),
  vocusTargetPicker: document.querySelector("#vocus-target-picker"),
  vocusEnvironment: document.querySelector("#vocus-environment"),
  miptofForm: document.querySelector("#miptof-panel"),
  miptofIsotopes: document.querySelector("#miptof-isotopes"),
  miptofIsotopePicker: document.querySelector("#miptof-isotope-picker"),
  miptofEnvironment: document.querySelector("#miptof-environment"),
  reagentOptions: document.querySelector("#reagent-options"),
  downloadGenerated: document.querySelector("#download-generated"),
  fileSummary: document.querySelector("#file-summary"),
  resetApplication: document.querySelector("#reset-application"),
  companionPanel: document.querySelector("#companion-panel"),
  companionInput: document.querySelector("#companion-input"),
  companionResults: document.querySelector("#companion-results"),
  hdfSearchPanel: document.querySelector("#hdf-search-panel"),
  hdfSearch: document.querySelector("#hdf-search"),
  hdfSearchButton: document.querySelector("#hdf-search-button"),
  hdfSearchResults: document.querySelector("#hdf-search-results"),
  hdfSearchNavigation: document.querySelector("#hdf-search-navigation"),
  hdfSearchCount: document.querySelector("#hdf-search-count"),
  hdfSearchPosition: document.querySelector("#hdf-search-position"),
  hdfSearchPrevious: document.querySelector("#hdf-search-previous"),
  hdfSearchNext: document.querySelector("#hdf-search-next"),
  expandHdf: document.querySelector("#expand-hdf"),
  metadataEmpty: document.querySelector("#metadata-empty"),
  metadataContent: document.querySelector("#metadata-content"),
  datasetSearch: document.querySelector("#dataset-search"),
  datasetList: document.querySelector("#dataset-list"),
  qualityContent: document.querySelector("#quality-content"),
  candidateSelect: document.querySelector("#candidate-select"),
  aggregationSelect: document.querySelector("#aggregation-select"),
  scaleSelect: document.querySelector("#scale-select"),
  resetView: document.querySelector("#reset-view"),
  rangeMin: document.querySelector("#range-min"),
  rangeMax: document.querySelector("#range-max"),
  applyRange: document.querySelector("#apply-range"),
  clearRange: document.querySelector("#clear-range"),
  exportCsv: document.querySelector("#export-csv"),
  visibleRangeLabel: document.querySelector("#visible-range-label"),
  chartMessage: document.querySelector("#chart-message"),
  chart: document.querySelector("#spectrum-chart"),
  expandSpectrum: document.querySelector("#expand-spectrum"),
  spectrumSource: document.querySelector("#spectrum-source"),
  sourceBadge: document.querySelector("#source-badge"),
  spectrumStats: document.querySelector("#spectrum-stats"),
  decimationNote: document.querySelector("#decimation-note"),
  peakTableBody: document.querySelector("#peak-table-body"),
  dftMode: document.querySelector("#dft-mode"),
  fftMode: document.querySelector("#fft-mode"),
  transformRun: document.querySelector("#transform-run"),
  transformRemoveMean: document.querySelector("#transform-remove-mean"),
  transformHann: document.querySelector("#transform-hann"),
  transformScale: document.querySelector("#transform-scale"),
  transformEmpty: document.querySelector("#transform-empty"),
  transformChart: document.querySelector("#transform-chart"),
  transformSummary: document.querySelector("#transform-summary"),
  expandTransform: document.querySelector("#expand-transform"),
  timeMassMin: document.querySelector("#time-mass-min"),
  timeMassMax: document.querySelector("#time-mass-max"),
  timeMin: document.querySelector("#time-min"),
  timeMax: document.querySelector("#time-max"),
  loadTimeSeries: document.querySelector("#load-time-series"),
  clearTimeRange: document.querySelector("#clear-time-range"),
  timeSeriesMessage: document.querySelector("#time-series-message"),
  timeSeriesChart: document.querySelector("#time-series-chart"),
  timeSeriesSummary: document.querySelector("#time-series-summary"),
  expandEit: document.querySelector("#expand-eit"),
  toast: document.querySelector("#toast"),
  loadingOverlay: document.querySelector("#loading-overlay"),
  loadingLabel: document.querySelector("#loading-label"),
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showLoading(label) {
  els.loadingLabel.textContent = label;
  els.loadingOverlay.classList.remove("hidden");
}

function hideLoading() {
  els.loadingOverlay.classList.add("hidden");
}

let toastTimer = null;
function toast(message, kind = "normal") {
  clearTimeout(toastTimer);
  els.toast.textContent = message;
  els.toast.classList.toggle("error", kind === "error");
  els.toast.classList.add("visible");
  toastTimer = setTimeout(() => els.toast.classList.remove("visible"), 4200);
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = {};
  }
  if (!response.ok) {
    throw new Error(payload.error || `Request failed (${response.status})`);
  }
  return payload;
}

function formatNumber(value, digits = 4) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  const absolute = Math.abs(number);
  if ((absolute >= 1e6 || (absolute > 0 && absolute < 1e-3))) {
    return number.toExponential(3);
  }
  return new Intl.NumberFormat(undefined, {
    maximumFractionDigits: digits,
  }).format(number);
}

function compactValue(value) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  return String(value);
}

function setControlsEnabled(enabled) {
  [
    els.candidateSelect,
    els.scaleSelect,
    els.resetView,
    els.rangeMin,
    els.rangeMax,
    els.applyRange,
    els.clearRange,
    els.timeMassMin,
    els.timeMassMax,
    els.timeMin,
    els.timeMax,
    els.loadTimeSeries,
    els.clearTimeRange,
  ].forEach((element) => {
    element.disabled = !enabled;
  });
  els.exportCsv.classList.toggle("disabled", !enabled);
  if (!enabled) els.aggregationSelect.disabled = true;
  els.resetApplication.disabled = !state.fileId;
}

function provenanceLabel(provenance) {
  if (provenance === "synthetic example") return "SYNTHETIC EXAMPLE";
  if (provenance === "synthetic generator") return "SYNTHETIC · NOT VALIDATED";
  if (provenance === "browser upload") return "LOADED HDF5";
  return "LOCAL HDF5";
}

function renderFileSummary(file) {
  els.fileSummary.innerHTML = `
    <span class="eyebrow">OPEN FILE</span>
    <div class="file-name"><strong>${escapeHtml(file.display_name)}</strong></div>
    <div class="summary-grid">
      <div><span>Size</span><strong>${escapeHtml(file.size_human)}</strong></div>
      <div><span>Provenance</span><strong>${escapeHtml(file.provenance)}</strong></div>
      <div><span>Datasets</span><strong>${formatNumber(file.dataset_count, 0)}</strong></div>
      <div><span>Groups</span><strong>${formatNumber(file.group_count, 0)}</strong></div>
    </div>
  `;
  els.fileSummary.classList.remove("hidden");
  els.activeFileTitle.textContent = file.display_name;
  els.sourceBadge.textContent = provenanceLabel(file.provenance);
  els.sourceBadge.className = `source-badge${file.provenance.startsWith("synthetic") ? " synthetic" : ""}`;
}

function renderCompanions(context) {
  els.companionPanel.classList.remove("hidden");
  const files = context?.files || [];
  if (!files.length) {
    els.companionResults.innerHTML = '<div class="empty-panel">No related companion files have been found yet. Add files from the same instrument-run folder.</div>';
    return;
  }
  els.companionResults.innerHTML = files.map(file => {
    const evidence = (file.evidence || []).map(item => item.detail).join(" · ") || "No direct relationship established";
    const warning = file.details?.warning ? ` · ${file.details.warning}` : "";
    return `<article class="companion-item relation-${escapeHtml(file.relation)}"><strong>${escapeHtml(file.name)}</strong><span>${escapeHtml(file.category)} · Relationship: ${escapeHtml(file.relation)}</span><span>${escapeHtml(evidence + warning)}</span></article>`;
  }).join("");
}

async function addCompanionFiles(files) {
  if (!state.fileId || !files?.length) return;
  showLoading("Reading companion files and correlating run evidence…");
  try {
    const data = new FormData();
    [...files].forEach(file => data.append("files", file));
    const payload = await fetchJson(`/api/file/${encodeURIComponent(state.fileId)}/companions`, {method:"POST", body:data});
    state.manifest.companion_context = payload.companion_context;
    renderCompanions(payload.companion_context);
    toast(`${payload.companion_context.files.length} companion file relationship(s) inventoried.`);
  } catch (error) { toast(error.message, "error"); }
  finally { hideLoading(); els.companionInput.value = ""; }
}

async function searchHdf5() {
  const query = els.hdfSearch.value.trim();
  if (!state.fileId || query.length < 2) { toast("Enter at least two characters to search.", "error"); return; }
  try {
    const payload = await fetchJson(`/api/file/${encodeURIComponent(state.fileId)}/search?q=${encodeURIComponent(query)}`);
    state.hdfMatches = payload.matches;
    state.hdfMatchIndex = payload.matches.length ? 0 : -1;
    els.hdfSearchResults.innerHTML = payload.matches.length ? payload.matches.map((item, index) =>
      `<article class="search-result" data-search-index="${index}" tabindex="-1"><strong>${escapeHtml(item.name || item.path)}</strong><span>${escapeHtml(item.kind)} · ${escapeHtml(item.path)}</span><span>${escapeHtml(item.value)}</span></article>`
    ).join("") : '<div class="empty-panel">No matching HDF5 strings were found.</div>';
    els.hdfSearchNavigation.classList.toggle("hidden", !payload.matches.length);
    els.hdfSearchCount.textContent = `${payload.count}${payload.limited ? "+" : ""} match${payload.count === 1 ? "" : "es"}`;
    focusHdfMatch(0);
    toast(`${payload.count} HDF5 match${payload.count === 1 ? "" : "es"} found.`);
  } catch (error) { toast(error.message, "error"); }
}

function focusHdfMatch(offset) {
  const total = state.hdfMatches.length;
  if (!total) { els.hdfSearchPosition.textContent = "0 / 0"; return; }
  state.hdfMatchIndex = (state.hdfMatchIndex + offset + total) % total;
  els.hdfSearchPosition.textContent = `${state.hdfMatchIndex + 1} / ${total}`;
  els.hdfSearchResults.querySelectorAll(".search-result").forEach((node, index) => node.classList.toggle("current-match", index === state.hdfMatchIndex));
  els.hdfSearchResults.querySelector(`[data-search-index="${state.hdfMatchIndex}"]`)?.scrollIntoView({block:"nearest", behavior:"smooth"});
}

async function resetApplication() {
  const fileId = state.fileId;
  if (fileId) {
    try { await fetchJson(`/api/file/${encodeURIComponent(fileId)}`, {method:"DELETE"}); }
    catch (error) { console.warn(error); }
  }
  state.fileId = null; state.manifest = null; state.spectrum = null; state.candidateId = null;
  state.fullRange = null; state.datasetQuery = ""; state.timeSeries = null; state.hdfMatches = []; state.hdfMatchIndex = -1;
  appliedInstrument = null; acquisitionLocked = false;
  resetDetectionStudy();
  els.activeFileTitle.textContent = "No HDF5 file open";
  document.querySelector("#data-source-title").textContent = "Open an HDF5 file";
  els.fileSummary.classList.add("hidden"); els.fileSummary.innerHTML = "";
  els.companionPanel.classList.add("hidden"); els.companionResults.innerHTML = "";
  els.hdfSearchPanel.classList.add("hidden"); els.hdfSearchResults.innerHTML = ""; els.hdfSearch.value = "";
  els.hdfSearchNavigation.classList.add("hidden");
  els.metadataContent.innerHTML = ""; els.metadataEmpty.classList.remove("hidden");
  els.datasetList.innerHTML = ""; els.datasetSearch.value = "";
  els.qualityContent.innerHTML = '<div class="empty-panel">Open a file to see calibration and data-quality notes.</div>';
  els.candidateSelect.innerHTML = "<option>No compatible dataset loaded</option>";
  els.rangeMin.value = ""; els.rangeMax.value = ""; els.pathInput.value = "";
  els.timeMassMin.value = ""; els.timeMassMax.value = ""; els.timeMin.value = ""; els.timeMax.value = "";
  els.chart.classList.add("hidden"); els.chart.innerHTML = "";
  els.chartMessage.classList.remove("hidden"); els.chartMessage.innerHTML = '<div class="chart-placeholder"><span class="spectrum-mark" aria-hidden="true"></span><strong>No spectrum loaded</strong><p>Load a compatible HDF5 file from the panel on the left.</p></div>';
  els.timeSeriesChart.classList.add("hidden"); els.timeSeriesChart.innerHTML = "";
  els.timeSeriesMessage.classList.remove("hidden"); els.timeSeriesMessage.textContent = "Open a time-resolved HDF5 dataset to inspect its acquisition history.";
  els.timeSeriesSummary.classList.add("hidden");
  els.expandSpectrum.disabled = true; els.expandEit.disabled = true; els.expandTransform.disabled = true;
  els.spectrumSource.textContent = "Open an HDF5 file to begin."; els.sourceBadge.textContent = "NO SOURCE"; els.sourceBadge.className = "source-badge empty";
  els.visibleRangeLabel.textContent = "Full range"; els.downloadGenerated.classList.add("hidden");
  setControlsEnabled(false); applyInstrumentFamilyConfiguration("unknown"); activateGeneratorPanel("open-panel");
  toast("Application reset. The loaded HDF5 session was cleared.");
}

const categoryLabels = {
  instrument: "Instrument",
  environment: "Environment & location",
  acquisition: "Acquisition",
  calibration: "Mass calibration",
  other: "Other metadata",
};

function renderMetadata(metadata) {
  els.metadataContent.replaceChildren();
  let total = 0;
  Object.entries(categoryLabels).forEach(([category, label], index) => {
    const items = metadata[category] || [];
    if (!items.length) return;
    total += items.length;
    const details = document.createElement("details");
    details.className = "metadata-group";
    details.open = index < 4 && category !== "other";
    details.innerHTML = `
      <summary>${escapeHtml(label)} <span class="metadata-count">${items.length}</span></summary>
      <dl class="metadata-list">
        ${items
          .map(
            (item) => `
            <div class="metadata-row">
              <dt>
                ${escapeHtml(item.name)}
                <span class="metadata-path">${escapeHtml(item.path)}</span>
              </dt>
              <dd>${escapeHtml(compactValue(item.value))}</dd>
            </div>`,
          )
          .join("")}
      </dl>`;
    els.metadataContent.append(details);
  });
  els.metadataEmpty.classList.toggle("hidden", total > 0);
}

function renderDatasets() {
  const datasets = state.manifest?.datasets || [];
  const query = state.datasetQuery.trim().toLowerCase();
  const filtered = query
    ? datasets.filter((item) => {
        const haystack = `${item.path} ${item.dtype} ${item.units || ""}`.toLowerCase();
        return haystack.includes(query);
      })
    : datasets;
  if (!filtered.length) {
    els.datasetList.innerHTML = `<div class="empty-panel">${datasets.length ? "No matching datasets." : "No datasets were inventoried."}</div>`;
    return;
  }
  els.datasetList.innerHTML = filtered
    .slice(0, 750)
    .map((item) => {
      const shape = item.shape.length ? `[${item.shape.join(" × ")}]` : "scalar";
      return `
        <article class="dataset-card">
          <span class="dataset-path">${escapeHtml(item.path)}</span>
          <div class="dataset-meta">
            <span>${escapeHtml(shape)}</span>
            <span>${escapeHtml(item.dtype)}</span>
            <span>${formatNumber(item.size, 0)} values</span>
            ${item.units ? `<span>${escapeHtml(item.units)}</span>` : ""}
            ${item.compression ? `<span>${escapeHtml(item.compression)}</span>` : ""}
          </div>
        </article>`;
    })
    .join("");
}

function renderQuality(manifest) {
  const candidates = manifest.spectrum_candidates || [];
  const messages = [];
  const context = manifest.instrument_context || {};
  if (context.family === "vocus" || context.family === "miptof") {
    const label = context.family === "vocus" ? "Vocus CI-TOF" : "mipTOF";
    messages.push({ok:true, text:`Instrument-family evidence indicates ${label}; its Data Source panel was selected automatically.`});
  } else {
    messages.push({ok:false, text:"No unambiguous Vocus or mipTOF instrument-family metadata was found; the Open HDF5 panel remains selected."});
  }
  if ((context.suggested_targets || []).length) {
    messages.push({ok:true, text:`Explicit HDF5 target metadata supplied: ${context.suggested_targets.join(", ")}. The corresponding target field was populated from metadata, not inferred from spectral peaks.`});
  } else {
    messages.push({ok:false, text:"No explicit target, analyte, compound, substance, isotope or element metadata was found. Target fields were left blank."});
  }
  if (candidates.length) {
    const recommended = candidates[0];
    messages.push({
      ok: true,
      text: `Detected spectrum source: ${recommended.label}. ${formatNumber(recommended.sample_count, 0)} samples; ${recommended.mode === "vector" ? "stored spectrum" : "multidimensional data aggregated along the last axis"}.`,
    });
    if (!recommended.warning) {
      messages.push({
        ok: true,
        text: `A compatible x-axis was found at ${recommended.x_path}. Values are displayed as stored; the viewer does not recalibrate them.`,
      });
    }
  }
  (manifest.warnings || []).forEach((text) => messages.push({ ok: false, text }));
  if (!messages.length) {
    messages.push({ ok: true, text: "No structural warnings were generated during the initial inventory." });
  }
  messages.push({
    ok: false,
    text: "A visible peak is an observation, not a compound identification. Formula assignment, adduct interpretation, and confidence require a validated analytical method.",
  });
  els.qualityContent.innerHTML = messages
    .map(
      (message) => `<div class="quality-item${message.ok ? " quality-ok" : ""}">${escapeHtml(message.text)}</div>`,
    )
    .join("");
}

function renderCandidates(candidates, recommendedId) {
  els.candidateSelect.replaceChildren();
  candidates.forEach((candidate) => {
    const option = document.createElement("option");
    option.value = candidate.id;
    option.textContent = candidate.label;
    option.selected = candidate.id === recommendedId;
    els.candidateSelect.append(option);
  });
  state.candidateId = recommendedId || candidates[0]?.id || null;
  updateAggregationControl();
}

function selectedCandidate() {
  return (state.manifest?.spectrum_candidates || []).find(
    (candidate) => candidate.id === state.candidateId,
  );
}

function updateAggregationControl() {
  const candidate = selectedCandidate();
  const aggregated = candidate?.mode === "sum_last_axis";
  els.aggregationSelect.disabled = !aggregated;
  if (!aggregated) els.aggregationSelect.value = "sum";
}

async function acceptOpenResponse(payload) {
  state.fileId = payload.file_id;
  state.manifest = payload.manifest;
  state.spectrum = null;
  state.fullRange = null;
  state.datasetQuery = "";
  state.timeSeries = null;
  els.datasetSearch.value = "";
  els.rangeMin.value = "";
  els.rangeMax.value = "";
  els.downloadGenerated.classList.add("hidden");
  if (!(payload.generation_summary && detectionStudyInput)) resetDetectionStudy();
  applyDetectedInstrumentContext(payload.manifest.instrument_context || {});
  applyAcquisitionMode(payload.manifest);
  renderFileSummary(payload.manifest.file);
  renderCompanions(payload.manifest.companion_context || {files:[]});
  els.hdfSearchPanel.classList.remove("hidden");
  renderMetadata(payload.manifest.metadata);
  renderDatasets();
  renderQuality(payload.manifest);
  renderCandidates(
    payload.manifest.spectrum_candidates || [],
    payload.manifest.recommended_candidate_id,
  );
  const hasSpectrum = Boolean(state.candidateId);
  setControlsEnabled(hasSpectrum);
  els.resetApplication.disabled = false;
  if (hasSpectrum) {
    await loadSpectrum({ preserveFullRange: false });
  } else {
    showChartError("No compatible spectrum pair was detected. Metadata and dataset inventory remain available.");
  }
}

function resetDetectionStudy() {
  detectionStudyInput = null;
  detectionStudyResult = null;
  ['detection-analyte','detection-formula','detection-mz','detection-unit','detection-matrix','detection-calibration','detection-blanks','detection-lod','detection-loq'].forEach(id => {
    document.querySelector(`#${id}`).value = '';
  });
  document.querySelector('#detection-export').disabled = true;
  document.querySelector('#detection-result').innerHTML = '<strong>No detection-capability study applied.</strong><span>Enter analyte-specific calibration and blank data. No example analyte is assumed.</span>';
}

function syncDetectionIdentity(target, family) {
  if (!target) return;
  const catalog = state.config?.generator_catalog || {};
  if (family === 'miptof') {
    const item = (catalog.isotopes || []).find(entry => entry.key.toUpperCase() === target.toUpperCase());
    document.querySelector('#detection-analyte').value = item?.key || target;
    document.querySelector('#detection-formula').value = item?.key || target;
    document.querySelector('#detection-mz').value = item?.mass ?? '';
  } else {
    const item = (catalog.targets || []).find(entry => entry.key.toUpperCase() === target.toUpperCase());
    document.querySelector('#detection-analyte').value = item?.name || target;
    document.querySelector('#detection-formula').value = item?.formula || '';
    document.querySelector('#detection-mz').value = '';
  }
}

function activateGeneratorPanel(panelId) {
  document.querySelectorAll(".generator-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.generatorPanel === panelId);
  });
  document.querySelectorAll(".generator-panel").forEach((panel) => panel.classList.toggle("active", panel.id === panelId));
}

function applyDetectedInstrumentContext(context) {
  appliedInstrument = null;
  document.querySelector('#configuration-enabled').checked = false;
  const targets = Array.isArray(context.suggested_targets) ? context.suggested_targets : [];
  // Never carry a target from the previously opened file into a new file.
  els.vocusTargets.value = "";
  els.miptofIsotopes.value = "";
  const familyName = context.family === 'vocus' ? 'Vocus CI-TOF' : context.family === 'miptof' ? 'mipTOF' : 'Unknown instrument family';
  document.querySelector('#detected-instrument-family').textContent = familyName;
  document.querySelector('#detected-instrument-reason').textContent = `${context.confidence || 'No explicit evidence'}. ${context.limitations || ''}`;
  const badge = document.querySelector('#detected-instrument-badge');
  badge.textContent = context.family === 'vocus' ? 'VOCUS' : context.family === 'miptof' ? 'mipTOF' : 'UNKNOWN';
  badge.classList.toggle('empty', context.family !== 'vocus' && context.family !== 'miptof');
  document.querySelector('#data-source-title').textContent = context.family === 'vocus' ? 'Vocus HDF5 selected' : context.family === 'miptof' ? 'mipTOF HDF5 selected' : 'Open an HDF5 file';
  applyInstrumentFamilyConfiguration(context.family);
  if (context.family === "vocus") {
    activateGeneratorPanel("vocus-panel");
    if (targets.length) els.vocusTargets.value = targets.join(", ");
    if (targets.length) syncDetectionIdentity(targets[0], 'vocus');
    toast(targets.length ? "Vocus metadata and explicit target information detected in the HDF5 file." : "Vocus instrument selected; no explicit target identity was found.");
  } else if (context.family === "miptof") {
    activateGeneratorPanel("miptof-panel");
    if (targets.length) els.miptofIsotopes.value = targets.join(", ");
    if (targets.length) syncDetectionIdentity(targets[0], 'miptof');
    toast(targets.length ? "mipTOF metadata and explicit isotope or element targets detected in the HDF5 file." : "mipTOF instrument selected; no explicit target identity was found.");
  } else {
    activateGeneratorPanel("open-panel");
  }
}

function applyAcquisitionMode(manifest) {
  const wasLocked=acquisitionLocked;
  acquisitionLocked=Boolean(manifest.acquisition_locked);
  const snapshot=manifest.acquisition_context||{};
  const display=record=>record?.value===null||record?.value===undefined ? (record?.status||'Not recorded') : String(record.value);
  const fields={'vocus-reagent':'reagent','vocus-targets':'targets','vocus-environment':'environment','miptof-isotopes':'targets','miptof-environment':'environment'};
  document.querySelectorAll('.generator-form input,.generator-form textarea,.generator-form select,.generator-form button,#instrument-form input,#instrument-form select,#instrument-form button').forEach(el=>el.disabled=acquisitionLocked);
  document.querySelectorAll('.generator-tab').forEach(el=>el.disabled=acquisitionLocked && el.dataset.generatorPanel!=='open-panel');
  document.querySelector('#acquisition-notice').classList.toggle('hidden',!acquisitionLocked);
  document.querySelector('#configuration-lock-notice').classList.toggle('hidden',!acquisitionLocked);
  document.querySelectorAll('.synthetic-notice').forEach(el=>el.classList.toggle('hidden',acquisitionLocked));
  document.querySelectorAll('.generator-form button[type="submit"]').forEach(el=>el.classList.toggle('hidden',acquisitionLocked));
  if(acquisitionLocked){
    appliedInstrument=null;
    for(const [id,key] of Object.entries(fields)){
      const el=document.querySelector('#'+id);el.value=display(snapshot[key]);el.title=snapshot[key]?.source||'No unambiguous acquisition metadata found';
    }
    instrumentFields.forEach(field=>{
      const record=snapshot.settings?.[field[1]];const input=document.querySelector('#instrument-'+field[1]);
      input.value=record?.value!==null && Number.isFinite(Number(record?.value)) ? Number(record.value) : '';
      input.placeholder=record?.status||'Not recorded';input.title=record?.source||'See the Parameters tab for original metadata';
      input.closest('label').querySelector('.field-meta').textContent=record?.status||'Not recorded';
    });
    for(const [id,key] of [['configuration-reagent','reagent'],['configuration-state','state']]){
      const select=document.querySelector('#'+id);select.querySelectorAll('[data-snapshot]').forEach(o=>o.remove());
      const opt=document.createElement('option');opt.dataset.snapshot='true';opt.value='recorded';opt.textContent=display(snapshot[key]);select.append(opt);select.value='recorded';
    }
    document.querySelector('#configuration-enabled').checked=false;
    document.querySelector('#configuration-dirty').textContent='Imported acquisition — read-only. Unknown settings remain Not recorded.';
  } else {
    if(wasLocked){
      instrumentFields.forEach(field=>{const input=document.querySelector('#instrument-'+field[1]);input.value=field[3];input.placeholder='';input.title='';input.closest('label').querySelector('.field-meta').textContent=(field[6]?'MODELLED EFFECT':'CONTEXT ONLY')+' · Default '+field[3];});
      document.querySelectorAll('[data-snapshot]').forEach(el=>el.remove());
      document.querySelector('#configuration-reagent').value=snapshot.reagent?.value||'I-';
      document.querySelector('#configuration-state').value='ready';
      els.vocusReagent.value=snapshot.reagent?.value||'I-';
      els.vocusEnvironment.value=snapshot.environment?.value||'H2O, N2, O2, CO2';
      els.miptofEnvironment.value=snapshot.environment?.value||'N2, O2, CO2, Ar, Fe';
    }
    applyInstrumentFamilyConfiguration(manifest.instrument_context?.family);
  }
}

function applyInstrumentFamilyConfiguration(family) {
  const mip = family === 'miptof';
  document.querySelector('#configuration-reagent-field').classList.toggle('hidden', mip);
  document.querySelectorAll('[data-instrument-group]').forEach(group => {
    group.classList.toggle('hidden', mip && ['Reagent-ion source','Reaction chamber'].includes(group.dataset.instrumentGroup));
  });
  const enabled = document.querySelector('#configuration-enabled');
  enabled.disabled = mip;
  if (mip) {
    enabled.checked = false;
    appliedInstrument = null;
    document.querySelector('#configuration-dirty').textContent = 'mipTOF context loaded. Vocus reagent-ion response modelling is disabled.';
  } else {
    document.querySelector('#configuration-dirty').textContent = family === 'vocus' ? 'Vocus context loaded. Response model remains off until enabled.' : 'No instrument family detected. Response model remains off.';
  }
}

function appendCommaValue(element, value) {
  const items = element.value.split(",").map((item) => item.trim()).filter(Boolean);
  if (!items.some((item) => item.toUpperCase() === value.toUpperCase())) items.push(value);
  element.value = items.join(", ");
}

function populateGeneratorCatalog(catalog) {
  els.reagentOptions.innerHTML = (catalog.reagents || [])
    .map((item) => `<option value="${escapeHtml(item.formula)}">${escapeHtml(item.label)}</option>`)
    .join("");
  const grouped = new Map();
  (catalog.targets || []).forEach((item) => {
    if (!grouped.has(item.class)) grouped.set(item.class, []);
    grouped.get(item.class).push(item);
  });
  els.vocusTargetPicker.innerHTML = `<option value="">Select a substance…</option>${[...grouped.entries()]
    .map(([group, items]) => `<optgroup label="${escapeHtml(group)}">${items
      .map((item) => `<option value="${escapeHtml(item.key)}">${escapeHtml(item.name)} · ${escapeHtml(item.formula)}</option>`)
      .join("")}</optgroup>`)
    .join("")}`;
  els.miptofIsotopePicker.innerHTML = `<option value="">Select an isotope…</option>${(catalog.isotopes || [])
    .map((item) => `<option value="${escapeHtml(item.key)}">${escapeHtml(item.label)} · m/z ${formatNumber(item.mass, 6)}</option>`)
    .join("")}`;
}

async function generateSynthetic(instrument, payload) {
  if(acquisitionLocked){toast("Start a new simulation to edit acquisition settings.","error");return;}
  const label = instrument === "vocus" ? "Vocus CI-TOF" : "mipTOF";
  if (!document.querySelector("#instrument-form").reportValidity()) return;
  try { appliedInstrument = document.querySelector("#configuration-enabled").checked ? instrumentSettings() : null; } catch(error) { toast(error.message, "error"); return; }
  showLoading(`Generating synthetic ${label} HDF5…`);
  try {
    const response = await fetchJson(`/api/generate/${instrument}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({...payload, ...(instrument === 'vocus' ? {instrument_configuration: instrumentSettings()} : {}), ...(detectionStudyInput ? {detection_study:detectionStudyInput} : {})}),
    });
    await acceptOpenResponse(response);
    els.downloadGenerated.href = response.download_url;
    els.downloadGenerated.download = response.manifest.file.display_name;
    els.downloadGenerated.classList.remove("hidden");
    toast(`${label} synthetic HDF5 generated and opened. Not measured data.`);
  } catch (error) {
    toast(error.message, "error");
  } finally {
    hideLoading();
  }
}

async function openLocalPath(path) {
  showLoading("Inspecting HDF5 structure…");
  try {
    const payload = await fetchJson("/api/open-path", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    });
    await acceptOpenResponse(payload);
    toast("HDF5 file opened in read-only mode.");
  } catch (error) {
    toast(error.message, "error");
  } finally {
    hideLoading();
  }
}

async function openReviewedFile(path) {
  showLoading("Opening selected HDF5 file…");
  try {
    const payload = await fetchJson("/api/open-reviewed", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    });
    document.querySelector('[data-workspace-target="spectrum-workspace"]').click();
    await acceptOpenResponse(payload);
    toast("Selected HDF5 file opened in read-only mode.");
  } finally {
    hideLoading();
  }
}

async function uploadFile(file) {
  if (!file) return;
  showLoading("Uploading locally and reading HDF5 structure…");
  try {
    const data = new FormData();
    data.append("file", file);
    const payload = await fetchJson("/api/upload", { method: "POST", body: data });
    await acceptOpenResponse(payload);
    toast("HDF5 file loaded into the local viewer cache.");
  } catch (error) {
    toast(error.message, "error");
  } finally {
    hideLoading();
    els.fileInput.value = "";
  }
}

async function openFixture() {
  showLoading("Opening synthetic reference fixture…");
  try {
    const payload = await fetchJson("/api/open-fixture", { method: "POST" });
    await acceptOpenResponse(payload);
    toast("Synthetic example opened. It is not measured instrument data.");
  } catch (error) {
    toast(error.message, "error");
  } finally {
    hideLoading();
  }
}

function currentAggregation() {
  return selectedCandidate()?.mode === "sum_last_axis"
    ? els.aggregationSelect.value
    : "sum";
}

function buildSpectrumUrl({ xMin = null, xMax = null, maxPoints = 30000 } = {}) {
  const params = new URLSearchParams({
    candidate: state.candidateId,
    aggregation: currentAggregation(),
    max_points: String(maxPoints),
  });
  if (appliedInstrument) params.set("instrument_configuration", JSON.stringify(appliedInstrument));
  if (detectionStudyInput) params.set("detection_study", JSON.stringify(detectionStudyInput));
  if (Number.isFinite(xMin)) params.set("x_min", String(xMin));
  if (Number.isFinite(xMax)) params.set("x_max", String(xMax));
  return `/api/file/${encodeURIComponent(state.fileId)}/spectrum?${params.toString()}`;
}

async function loadSpectrum({
  xMin = null,
  xMax = null,
  preserveFullRange = true,
  showBusy = true,
} = {}) {
  if (!state.fileId || !state.candidateId) return;
  if (showBusy) showLoading(xMin === null ? "Reading spectrum…" : "Reading focused mass window…");
  try {
    const spectrum = await fetchJson(buildSpectrumUrl({ xMin, xMax, maxPoints: 60000 }));
    state.spectrum = spectrum;
    if (!preserveFullRange || !state.fullRange) {
      state.fullRange = { ...spectrum.range };
    }
    renderSpectrum(spectrum, xMin !== null || xMax !== null);
    updateExportLink();
  } catch (error) {
    showChartError(error.message);
    toast(error.message, "error");
  } finally {
    if (showBusy) hideLoading();
  }
}

function chartLayout(spectrum, focused) {
  const xTitle = spectrum.candidate.x_path
    ? `Mass-to-charge ratio (${spectrum.candidate.x_units || "Th"})`
    : "Sample index";
  const yTitle = `Signal intensity (${spectrum.candidate.y_units || "a.u."})`;
  const range = focused ? [spectrum.range.min, spectrum.range.max] : undefined;
  const detectionShapes = detectionStudyResult && detectionStudyResult.lod_response != null ? [
    {type:'line', xref:'paper', x0:0, x1:1, y0:detectionStudyResult.lod_response, y1:detectionStudyResult.lod_response, line:{color:'#f0b75d',width:1.5,dash:'dot'}},
    {type:'line', xref:'paper', x0:0, x1:1, y0:detectionStudyResult.loq_response, y1:detectionStudyResult.loq_response, line:{color:'#68d79d',width:1.5,dash:'dash'}},
  ] : [];
  return {
    autosize: true,
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "#061820",
    margin: { l: 82, r: 28, t: 30, b: 96 },
    hovermode: "closest",
    dragmode: "zoom",
    font: { family: "Inter, system-ui, sans-serif", color: "#a9c1c8", size: 12 },
    xaxis: {
      title: { text: xTitle, standoff: 14, font: { color: "#b8ccd2" } },
      range,
      showgrid: true,
      gridcolor: "rgba(87, 138, 151, 0.18)",
      zeroline: false,
      linecolor: "#2b5663",
      tickcolor: "#2b5663",
      tickfont: { color: "#87a7b0" },
      rangeslider: {
        visible: true,
        thickness: 0.12,
        bgcolor: "#0a222b",
        bordercolor: "#244b57",
        borderwidth: 1,
      },
    },
    yaxis: {
      title: { text: yTitle, standoff: 12, font: { color: "#b8ccd2" } },
      type: els.scaleSelect.value,
      showgrid: true,
      gridcolor: "rgba(87, 138, 151, 0.18)",
      zeroline: false,
      linecolor: "#2b5663",
      tickcolor: "#2b5663",
      tickfont: { color: "#87a7b0" },
      exponentformat: "SI",
    },
    showlegend: false,
    shapes: detectionShapes,
  };
}

function renderSpectrum(spectrum, focused) {
  els.chartMessage.classList.add("hidden");
  els.chart.classList.remove("hidden");
  els.expandSpectrum.disabled = false;
  const trace = {
    x: spectrum.x,
    y: spectrum.y,
    type: "scattergl",
    mode: "lines",
    line: { color: "#54e0cf", width: 1.35 },
    hovertemplate:
      `<b>m/z</b> %{x:.7f}<br><b>Intensity</b> %{y:.7g}<extra></extra>`,
  };
  const config = {
    responsive: true,
    scrollZoom: true,
    displaylogo: false,
    toImageButtonOptions: {
      format: "png",
      filename: "tofshield-ada-spectrum",
      height: 900,
      width: 1600,
      scale: 2,
    },
    modeBarButtonsToRemove: ["lasso2d", "select2d"],
  };
  Plotly.react(els.chart, [trace], chartLayout(spectrum, focused), config).then(() => {
    bindPlotEvents();
  });

  const source = spectrum.candidate;
  const aggregation = source.mode === "sum_last_axis" ? ` · ${spectrum.aggregation} aggregation` : "";
  els.spectrumSource.textContent = `${source.y_path} vs ${source.x_path || "sample index"}${aggregation}`;
  els.visibleRangeLabel.textContent = `${formatNumber(spectrum.range.min, 6)} – ${formatNumber(spectrum.range.max, 6)} ${source.x_units || ""}`;
  els.rangeMin.placeholder = formatNumber(state.fullRange?.min ?? spectrum.range.min, 6);
  els.rangeMax.placeholder = formatNumber(state.fullRange?.max ?? spectrum.range.max, 6);
  const report = spectrum.configuration_report;
  document.querySelector("#configuration-report").textContent = report ? `${report.status}. Delay ${formatNumber(report.transport_delay_s)} s; response ${formatNumber(report.sample_response_fraction * 100)}%; multiplier ${formatNumber(report.signal_multiplier)}. Context-only: pressure, temperatures, reaction time, E/N, humidity, vacuum. ${report.limitations}` : "Stored-data analysis. Instrument response model is off; loaded HDF5 values remain unchanged.";
  els.sourceBadge.textContent = report ? "ILLUSTRATIVE CONFIGURED RESPONSE" : provenanceLabel(state.manifest.file.provenance);
  renderStats(spectrum);
  renderPeaks(spectrum.peaks || []);
  if (els.timeMassMin.value === "" || els.timeMassMax.value === "") {
    const peak = spectrum.peaks?.[0];
    const center = Number(peak?.centroid_mz ?? peak?.mz);
    if (Number.isFinite(center)) {
      const half = Math.max(Number(peak?.fwhm || 0.02), 0.02);
      els.timeMassMin.value = (center - half).toPrecision(8);
      els.timeMassMax.value = (center + half).toPrecision(8);
    } else {
      els.timeMassMin.value = Number(spectrum.range.min).toPrecision(8);
      els.timeMassMax.value = Number(spectrum.range.max).toPrecision(8);
    }
  }
  els.transformRun.disabled = false;
  els.transformChart.classList.add("hidden");
  els.transformSummary.classList.add("hidden");
  els.transformEmpty.classList.remove("hidden");
  els.transformEmpty.textContent = "Spectrum ready. Select an algorithm and calculate the transform.";
}

function highestPowerOfTwo(value) {
  let result = 1;
  while (result * 2 <= value) result *= 2;
  return result;
}

function uniformSpectrum(spectrum, maximumPoints) {
  const points = spectrum.x.map((x, index) => [Number(x), Number(spectrum.y[index])])
    .filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y))
    .sort((a, b) => a[0] - b[0]);
  const unique = [];
  for (const point of points) {
    if (!unique.length || point[0] > unique[unique.length - 1][0]) unique.push(point);
    else unique[unique.length - 1][1] = Math.max(unique[unique.length - 1][1], point[1]);
  }
  const count = highestPowerOfTwo(Math.min(maximumPoints, unique.length));
  if (count < 8) throw new Error('At least eight distinct mass-axis points are required.');
  const start = unique[0][0];
  const end = unique[unique.length - 1][0];
  const spacing = (end - start) / (count - 1);
  if (!(spacing > 0)) throw new Error('A finite increasing mass axis is required.');
  const values = new Array(count);
  let source = 0;
  for (let index = 0; index < count; index += 1) {
    const target = start + index * spacing;
    while (source + 1 < unique.length && unique[source + 1][0] < target) source += 1;
    const left = unique[source];
    const right = unique[Math.min(source + 1, unique.length - 1)];
    const fraction = right[0] === left[0] ? 0 : (target - left[0]) / (right[0] - left[0]);
    values[index] = left[1] + (right[1] - left[1]) * fraction;
  }
  if (els.transformRemoveMean.checked) {
    const mean = values.reduce((sum, value) => sum + value, 0) / count;
    for (let index = 0; index < count; index += 1) values[index] -= mean;
  }
  const window = new Array(count).fill(1);
  if (els.transformHann.checked) {
    for (let index = 0; index < count; index += 1) window[index] = 0.5 * (1 - Math.cos(2 * Math.PI * index / (count - 1)));
  }
  for (let index = 0; index < count; index += 1) values[index] *= window[index];
  return { values, spacing, windowSum: window.reduce((sum, value) => sum + value, 0), start, end };
}

function directDft(values) {
  const count = values.length;
  const real = new Array(count / 2 + 1);
  const imaginary = new Array(count / 2 + 1);
  for (let k = 0; k <= count / 2; k += 1) {
    let re = 0;
    let im = 0;
    for (let n = 0; n < count; n += 1) {
      const angle = -2 * Math.PI * k * n / count;
      re += values[n] * Math.cos(angle);
      im += values[n] * Math.sin(angle);
    }
    real[k] = re;
    imaginary[k] = im;
  }
  return { real, imaginary };
}

function fastFft(values) {
  const count = values.length;
  const real = values.slice();
  const imaginary = new Array(count).fill(0);
  for (let i = 1, j = 0; i < count; i += 1) {
    let bit = count >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) {
      [real[i], real[j]] = [real[j], real[i]];
      [imaginary[i], imaginary[j]] = [imaginary[j], imaginary[i]];
    }
  }
  for (let length = 2; length <= count; length <<= 1) {
    const angle = -2 * Math.PI / length;
    const stepReal = Math.cos(angle);
    const stepImaginary = Math.sin(angle);
    for (let offset = 0; offset < count; offset += length) {
      let twiddleReal = 1;
      let twiddleImaginary = 0;
      for (let j = 0; j < length / 2; j += 1) {
        const even = offset + j;
        const odd = even + length / 2;
        const oddReal = real[odd] * twiddleReal - imaginary[odd] * twiddleImaginary;
        const oddImaginary = real[odd] * twiddleImaginary + imaginary[odd] * twiddleReal;
        real[odd] = real[even] - oddReal;
        imaginary[odd] = imaginary[even] - oddImaginary;
        real[even] += oddReal;
        imaginary[even] += oddImaginary;
        const nextReal = twiddleReal * stepReal - twiddleImaginary * stepImaginary;
        twiddleImaginary = twiddleReal * stepImaginary + twiddleImaginary * stepReal;
        twiddleReal = nextReal;
      }
    }
  }
  return { real: real.slice(0, count / 2 + 1), imaginary: imaginary.slice(0, count / 2 + 1) };
}

function calculateTransform() {
  if (!state.spectrum) return;
  try {
    const maximum = transformMode === 'dft' ? 1024 : 8192;
    const prepared = uniformSpectrum(state.spectrum, maximum);
    const started = performance.now();
    const transformed = transformMode === 'dft' ? directDft(prepared.values) : fastFft(prepared.values);
    const elapsed = performance.now() - started;
    const count = prepared.values.length;
    const frequency = transformed.real.map((_, index) => index / (count * prepared.spacing));
    const magnitude = transformed.real.map((value, index) => {
      const base = Math.hypot(value, transformed.imaginary[index]) / prepared.windowSum;
      return index === 0 || index === count / 2 ? base : 2 * base;
    });
    const candidateIndexes = frequency.map((_, index) => index).slice(1).sort((a, b) => magnitude[b] - magnitude[a]).slice(0, 6);
    const dominant = candidateIndexes[0] || 0;
    const axisUnit = state.spectrum.candidate.x_path ? 'Th' : 'sample';
    const trace = {x: frequency, y: magnitude, type: 'scattergl', mode: 'lines', line: {color: '#54e0cf', width: 1.5}, hovertemplate: `<b>Frequency</b> %{x:.7g} cycles/${axisUnit}<br><b>Amplitude</b> %{y:.7g}<extra></extra>`};
    const layout = {autosize:true,paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'#061820',margin:{l:82,r:28,t:25,b:70},font:{family:'Inter, system-ui, sans-serif',color:'#a9c1c8',size:12},xaxis:{title:`Spatial frequency (cycles/${axisUnit})`,showgrid:true,gridcolor:'rgba(87,138,151,.18)',zeroline:false},yaxis:{title:'Fourier amplitude (a.u.)',type:els.transformScale.value,showgrid:true,gridcolor:'rgba(87,138,151,.18)',zeroline:false},showlegend:false};
    Plotly.react(els.transformChart,[trace],layout,{responsive:true,displaylogo:false,scrollZoom:true,toImageButtonOptions:{format:'png',filename:`tofshield-ada-${transformMode}`,height:800,width:1400,scale:2},modeBarButtonsToRemove:['lasso2d','select2d']});
    els.transformEmpty.classList.add('hidden');
    els.transformChart.classList.remove('hidden');
    els.transformSummary.classList.remove('hidden');
    els.expandTransform.disabled = false;
    const period = frequency[dominant] > 0 ? 1 / frequency[dominant] : null;
    els.transformSummary.innerHTML = `<div><span>Algorithm</span><strong>${transformMode === 'dft' ? 'Direct DFT' : 'Radix-2 FFT'}</strong></div><div><span>Uniform samples</span><strong>${count.toLocaleString()}</strong></div><div><span>Grid spacing</span><strong>${formatNumber(prepared.spacing,6)} ${axisUnit}</strong></div><div><span>Dominant non-DC frequency</span><strong>${formatNumber(frequency[dominant],6)} cycles/${axisUnit}</strong></div><div><span>Equivalent spacing</span><strong>${period ? formatNumber(period,6)+' '+axisUnit+'/cycle' : '—'}</strong></div><div><span>Calculation time</span><strong>${formatNumber(elapsed,4)} ms</strong></div>`;
  } catch (error) {
    els.transformChart.classList.add('hidden');
    els.transformSummary.classList.add('hidden');
    els.transformEmpty.classList.remove('hidden');
    els.transformEmpty.textContent = error.message;
    toast(error.message, 'error');
  }
}

let plotEventsBound = false;
function bindPlotEvents() {
  if (plotEventsBound) return;
  plotEventsBound = true;
  els.chart.on("plotly_relayout", (event) => {
    if (event["xaxis.range[0]"] !== undefined && event["xaxis.range[1]"] !== undefined) {
      const min = Number(event["xaxis.range[0]"]);
      const max = Number(event["xaxis.range[1]"]);
      if (Number.isFinite(min) && Number.isFinite(max)) {
        els.rangeMin.value = min.toPrecision(8);
        els.rangeMax.value = max.toPrecision(8);
        els.visibleRangeLabel.textContent = `${formatNumber(min, 6)} – ${formatNumber(max, 6)} ${state.spectrum?.candidate.x_units || ""}`;
        updateExportLink();
      }
    }
    if (event["xaxis.autorange"]) {
      els.rangeMin.value = "";
      els.rangeMax.value = "";
      const range = state.fullRange;
      if (range) {
        els.visibleRangeLabel.textContent = `${formatNumber(range.min, 6)} – ${formatNumber(range.max, 6)} ${state.spectrum?.candidate.x_units || ""}`;
      }
      updateExportLink();
    }
  });
  els.chart.on("plotly_click", (event) => {
    const point = event.points?.[0];
    if (!point) return;
    const mz = Number(point.x);
    els.timeMassMin.value = (mz - 0.05).toPrecision(8);
    els.timeMassMax.value = (mz + 0.05).toPrecision(8);
    toast(`Selected m/z ${formatNumber(point.x, 7)} · time-trace window prepared`);
  });
}

function showChartError(message) {
  els.chart.classList.add("hidden");
  els.chartMessage.classList.remove("hidden");
  els.chartMessage.innerHTML = `
    <div class="chart-placeholder">
      <span class="spectrum-mark" aria-hidden="true"></span>
      <strong>Spectrum unavailable</strong>
      <p>${escapeHtml(message)}</p>
    </div>`;
}

function renderStats(spectrum) {
  const values = [
    ["Raw points", formatNumber(spectrum.raw_point_count, 0)],
    ["Maximum", formatNumber(spectrum.stats.maximum, 6)],
    ["Mean", formatNumber(spectrum.stats.mean, 6)],
    ["Total signal", formatNumber(spectrum.stats.total, 6)],
  ];
  els.spectrumStats.innerHTML = values
    .map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong title="${escapeHtml(value)}">${escapeHtml(value)}</strong></div>`)
    .join("");
  const decimated = spectrum.displayed_point_count < spectrum.raw_point_count;
  els.decimationNote.classList.toggle("hidden", !decimated);
  if (decimated) {
    els.decimationNote.textContent = `Peak-preserving display reduction: ${formatNumber(spectrum.raw_point_count, 0)} source points → ${formatNumber(spectrum.displayed_point_count, 0)} plotted points. Use “Load exact window” for a denser view of a selected interval.`;
  }
}

function renderPeaks(peaks) {
  if (!peaks.length) {
    els.peakTableBody.innerHTML = `<tr><td colspan="9" class="empty-cell">No local maxima found</td></tr>`;
    return;
  }
  els.peakTableBody.innerHTML = peaks
    .map(
      (peak, index) => `
      <tr data-mz="${peak.centroid_mz ?? peak.mz}">
        <td>${index + 1}</td>
        <td>${escapeHtml(formatNumber(peak.centroid_mz ?? peak.mz, 8))}</td>
        <td>${escapeHtml(formatNumber(peak.intensity, 6))}</td>
        <td>${peak.fwhm == null ? '—' : escapeHtml(formatNumber(peak.fwhm, 7))}</td>
        <td>${peak.resolving_power == null ? '—' : escapeHtml(formatNumber(peak.resolving_power, 6))}</td>
        <td><span class="peak-quality quality-${escapeHtml(String(peak.quality || 'unavailable').toLowerCase().replaceAll(' ','-'))}">${escapeHtml(peak.quality || 'Unavailable')}</span></td>
        <td>${peak.concentration == null ? '—' : `${escapeHtml(formatNumber(peak.concentration, 6))} ${escapeHtml(detectionStudyResult?.concentration_unit || '')}`}</td>
        <td>${peak.signal_to_noise == null ? '—' : escapeHtml(formatNumber(peak.signal_to_noise, 5))}</td>
        <td><span class="detection-status">${escapeHtml(peak.detection_status || 'Not evaluated')}</span></td>
      </tr>`,
    )
    .join("");
  els.peakTableBody.querySelectorAll("tr[data-mz]").forEach((row) => {
    row.addEventListener("click", () => {
      const mz = Number(row.dataset.mz);
      const fullSpan = (state.fullRange?.max || mz + 1) - (state.fullRange?.min || mz - 1);
      const halfWidth = Math.max(0.15, fullSpan / 800);
      const min = mz - halfWidth;
      const max = mz + halfWidth;
      els.rangeMin.value = min.toPrecision(8);
      els.rangeMax.value = max.toPrecision(8);
      els.timeMassMin.value = min.toPrecision(8);
      els.timeMassMax.value = max.toPrecision(8);
      Plotly.relayout(els.chart, { "xaxis.range": [min, max] });
      updateExportLink();
    });
  });
}

function rangeValues() {
  const min = els.rangeMin.value === "" ? null : Number(els.rangeMin.value);
  const max = els.rangeMax.value === "" ? null : Number(els.rangeMax.value);
  if ((min !== null && !Number.isFinite(min)) || (max !== null && !Number.isFinite(max))) {
    throw new Error("Enter finite numeric values for the focused range.");
  }
  if (min !== null && max !== null && min === max) {
    throw new Error("The beginning and end of the mass window must differ.");
  }
  return { min, max };
}

function updateExportLink() {
  if (!state.fileId || !state.candidateId) return;
  let range;
  try {
    range = rangeValues();
  } catch {
    range = { min: null, max: null };
  }
  const params = new URLSearchParams({
    candidate: state.candidateId,
    aggregation: currentAggregation(),
  });
  if (appliedInstrument) params.set("instrument_configuration", JSON.stringify(appliedInstrument));
  if (detectionStudyInput) params.set("detection_study", JSON.stringify(detectionStudyInput));
  if (range.min !== null) params.set("x_min", String(range.min));
  if (range.max !== null) params.set("x_max", String(range.max));
  els.exportCsv.href = `/api/file/${encodeURIComponent(state.fileId)}/export.csv?${params.toString()}`;
}

async function loadTimeSeries(fullPeriod = false) {
  if (!state.fileId || !state.candidateId) return;
  const massMin = Number(els.timeMassMin.value);
  const massMax = Number(els.timeMassMax.value);
  if (!Number.isFinite(massMin) || !Number.isFinite(massMax)) {
    toast("Enter a valid m/z interval for the time trace.", "error"); return;
  }
  if (massMin > massMax) { toast("The beginning of the m/z interval must not exceed its end.", "error"); return; }
  const params = new URLSearchParams({candidate:state.candidateId, aggregation:currentAggregation(), mass_min:String(massMin), mass_max:String(massMax), max_points:"5000"});
  if (!fullPeriod && els.timeMin.value !== "") params.set("time_min", els.timeMin.value);
  if (!fullPeriod && els.timeMax.value !== "") params.set("time_max", els.timeMax.value);
  showLoading("Reading time-resolved measurements…");
  try {
    const payload = await fetchJson(`/api/file/${encodeURIComponent(state.fileId)}/time-series?${params}`);
    state.timeSeries = payload;
    els.timeMin.placeholder = formatNumber(payload.time_range.min, 3);
    els.timeMax.placeholder = formatNumber(payload.time_range.max, 3);
    const shapes = (payload.events || []).filter(event => event.time >= payload.time_range.min && event.time <= payload.time_range.max).map(event => ({type:"line", x0:event.time, x1:event.time, yref:"paper", y0:0, y1:1, line:{color:"rgba(240,183,93,.65)",width:1,dash:"dot"}}));
    const annotations = (payload.events || []).filter(event => event.time >= payload.time_range.min && event.time <= payload.time_range.max).slice(0,20).map(event => ({x:event.time,y:1,yref:"paper",text:event.label,showarrow:true,arrowhead:2,ax:0,ay:-28,font:{size:10,color:"#e6c882"}}));
    Plotly.react(els.timeSeriesChart,[{x:payload.time,y:payload.intensity,type:"scattergl",mode:"lines",line:{color:"#f0b75d",width:1.5},hovertemplate:`<b>Time</b> %{x:.4g}<br><b>Signal</b> %{y:.7g}<extra></extra>`}],{autosize:true,paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"#061820",margin:{l:82,r:28,t:38,b:68},font:{family:"Inter, system-ui, sans-serif",color:"#a9c1c8",size:12},xaxis:{title:payload.time_units,showgrid:true,gridcolor:"rgba(87,138,151,.18)",zeroline:false},yaxis:{title:"Integrated signal",showgrid:true,gridcolor:"rgba(87,138,151,.18)",zeroline:false},shapes,annotations,showlegend:false},{responsive:true,scrollZoom:true,displaylogo:false,modeBarButtonsToRemove:["lasso2d","select2d"]});
    els.timeSeriesMessage.classList.add("hidden"); els.timeSeriesChart.classList.remove("hidden"); els.timeSeriesSummary.classList.remove("hidden");
    els.expandEit.disabled = false;
    els.timeSeriesSummary.textContent = `Stored m/z ${formatNumber(payload.mass_range.min,6)}–${formatNumber(payload.mass_range.max,6)} · ${payload.time.length.toLocaleString()} time points · ${payload.storage_interpretation} · ${payload.time_source || "acquisition index fallback"}. ${payload.limitations}`;
  } catch (error) {
    els.timeSeriesChart.classList.add("hidden"); els.timeSeriesMessage.classList.remove("hidden"); els.timeSeriesMessage.textContent = error.message; toast(error.message,"error");
  } finally { hideLoading(); }
}

function popupShell(title, body) {
  const popupClass = title.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-").replaceAll(/^-|-$/g, "");
  const popup = window.open("", `tofshield-${popupClass}`, "popup=yes,width=1280,height=880,resizable=yes,scrollbars=yes");
  if (!popup) { toast("The browser blocked the investigation window. Allow pop-ups for this local application.", "error"); return null; }
  popup.document.open();
  popup.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>${escapeHtml(title)}</title><link rel="stylesheet" href="/static/app.css"><link rel="stylesheet" href="/static/enhancements.css"><style>html,body{min-height:100%;margin:0}body{padding:18px 22px;background:#04151c;color:#d7eef2}.popout-shell{width:100%;max-width:none;margin:0}.popout-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}.popout-header h1{margin:2px 0 4px}.popout-controls{display:flex;gap:10px;flex-wrap:wrap;align-items:end;margin-bottom:8px}.popout-controls label{display:grid;gap:5px}.popout-chart{width:100%;height:calc(100vh - 235px);min-height:520px}.popout-content{display:grid;gap:14px}.popout-tabs{display:flex;gap:8px}.popout-panel{display:none}.popout-panel.active{display:block}.search-result.current-match{outline:2px solid #54e0cf}.hdf5-file-inspector{font-size:15px}.hdf5-file-inspector .metadata-row dt,.hdf5-file-inspector .metadata-row dd,.hdf5-file-inspector .dataset-card,.hdf5-file-inspector .quality-item{font-size:14px}.hdf5-file-inspector .metadata-path,.hdf5-file-inspector .dataset-meta{font-size:12px}</style></head><body class="${escapeHtml(popupClass)}"><main class="popout-shell"><header class="popout-header"><div><span class="eyebrow">TOFSHIELD ANALYTICAL WORKSPACE</span><h1>${escapeHtml(title)}</h1><p>${escapeHtml(state.manifest?.file?.display_name || state.manifest?.file?.name || els.activeFileTitle.textContent || "Open HDF5")}</p></div><button id="close-popout" class="button ghost">Close</button></header>${body}</main></body></html>`);
  popup.document.close();
  popup.Plotly = window.Plotly;
  popup.document.querySelector("#close-popout").addEventListener("click", () => popup.close());
  popup.focus();
  return popup;
}

function copyPlot(source, popup, targetId, axisTitles = {}) {
  const render = () => {
    if (!source?.data?.length || !popup.Plotly) return;
    const layout = JSON.parse(JSON.stringify(source.layout || {}));
    const target = popup.document.getElementById(targetId);
    const dimensions = () => ({
      width: Math.max(320, popup.innerWidth - 44),
      height: Math.max(420, popup.innerHeight - target.getBoundingClientRect().top - 34),
    });
    const size = dimensions();
    target.style.width = `${size.width}px`; target.style.height = `${size.height}px`;
    layout.autosize = false; layout.width = size.width; layout.height = size.height;
    layout.margin = {...(layout.margin || {}), l:92, r:34, t:24, b:88};
    layout.hovermode = "closest"; layout.hoverdistance = -1; layout.spikedistance = -1;
    layout.xaxis = {...(layout.xaxis || {}), title:{text:axisTitles.x || layout.xaxis?.title?.text || "Horizontal value",standoff:18},nticks:16,automargin:true,showspikes:true,spikesnap:"cursor",spikemode:"across+toaxis",spikedash:"dot",spikecolor:"#9bd7df",spikethickness:1};
    layout.yaxis = {...(layout.yaxis || {}), title:{text:axisTitles.y || layout.yaxis?.title?.text || "Vertical value",standoff:18},nticks:14,automargin:true,showspikes:true,spikesnap:"cursor",spikemode:"across+toaxis",spikedash:"dot",spikecolor:"#9bd7df",spikethickness:1};
    popup.Plotly.react(target, source.data, layout, {responsive:false,scrollZoom:true,displaylogo:false,displayModeBar:false});
    if (!popup.__plotResizeBound) {
      popup.__plotResizeBound = true;
      popup.addEventListener("resize", () => {
        const next = dimensions();
        target.style.width = `${next.width}px`; target.style.height = `${next.height}px`;
        popup.Plotly.relayout(target, {width:next.width,height:next.height});
      });
    }
  };
  if (popup.Plotly) render(); else popup.addEventListener("load", render, {once:true});
}

function openSpectrumWindow() {
  if (!state.spectrum) return;
  const popup = popupShell("Mass Spectrum", `<div class="popout-controls"><label>m/z from<input id="p-min" type="number" step="any" value="${escapeHtml(els.rangeMin.value)}"></label><label>m/z to<input id="p-max" type="number" step="any" value="${escapeHtml(els.rangeMax.value)}"></label><label>Y scale<select id="p-scale"><option value="linear">Linear</option><option value="log">Logarithmic</option></select></label><button id="p-apply" class="button primary">Load exact window</button><button id="p-full" class="button secondary">Full spectrum</button></div><div id="p-chart" class="popout-chart"></div>`);
  if (!popup) return;
  popup.document.querySelector("#p-scale").value = els.scaleSelect.value;
  const refresh = () => copyPlot(els.chart, popup, "p-chart", {x:"Mass-to-charge ratio (Th)",y:"Signal intensity (stored units)"}); refresh();
  popup.document.querySelector("#p-apply").addEventListener("click", async () => { const min=Number(popup.document.querySelector("#p-min").value), max=Number(popup.document.querySelector("#p-max").value); if(!Number.isFinite(min)||!Number.isFinite(max)||min>=max){toast("Enter a valid increasing m/z range.","error");return;} els.rangeMin.value=min;els.rangeMax.value=max;await loadSpectrum({xMin:min,xMax:max,preserveFullRange:true});refresh(); });
  popup.document.querySelector("#p-full").addEventListener("click", async () => { els.rangeMin.value="";els.rangeMax.value="";await loadSpectrum({preserveFullRange:false});popup.document.querySelector("#p-min").value="";popup.document.querySelector("#p-max").value="";refresh(); });
  popup.document.querySelector("#p-scale").addEventListener("change", event => { els.scaleSelect.value=event.target.value; Plotly.relayout(els.chart,{"yaxis.type":event.target.value,"yaxis.autorange":true});refresh(); });
}

function openEitWindow() {
  if (!state.timeSeries) return;
  const popup = popupShell("Extracted Ion Trace (EIT)", `<div class="popout-controls"><label>m/z from<input id="p-mass-min" type="number" step="any" value="${escapeHtml(els.timeMassMin.value)}"></label><label>m/z to<input id="p-mass-max" type="number" step="any" value="${escapeHtml(els.timeMassMax.value)}"></label><label>Time from<input id="p-time-min" type="number" step="any" value="${escapeHtml(els.timeMin.value)}"></label><label>Time to<input id="p-time-max" type="number" step="any" value="${escapeHtml(els.timeMax.value)}"></label><button id="p-load" class="button primary">Load ion trace</button><button id="p-full" class="button secondary">Full acquisition</button></div><div id="p-chart" class="popout-chart"></div><div id="p-summary" class="note-box">${escapeHtml(els.timeSeriesSummary.textContent)}</div>`);
  if (!popup) return;
  const refresh = () => { copyPlot(els.timeSeriesChart,popup,"p-chart",{x:"Acquisition time (seconds from start)",y:"Integrated ion signal (stored units)"}); popup.document.querySelector("#p-summary").textContent=els.timeSeriesSummary.textContent; }; refresh();
  popup.document.querySelector("#p-load").addEventListener("click", async () => { [[els.timeMassMin,"p-mass-min"],[els.timeMassMax,"p-mass-max"],[els.timeMin,"p-time-min"],[els.timeMax,"p-time-max"]].forEach(([main,id])=>main.value=popup.document.getElementById(id).value); await loadTimeSeries(false);refresh(); });
  popup.document.querySelector("#p-full").addEventListener("click", async () => { els.timeMin.value="";els.timeMax.value="";popup.document.querySelector("#p-time-min").value="";popup.document.querySelector("#p-time-max").value="";await loadTimeSeries(true);refresh(); });
}

function openTransformWindow() {
  if (els.transformChart.classList.contains("hidden")) return;
  const popup = popupShell("Fourier Analysis", `<div class="popout-controls"><button id="p-dft" class="button secondary">Direct Fourier transform</button><button id="p-fft" class="button secondary">Fast Fourier transform</button><label><input id="p-mean" type="checkbox"> Remove mean</label><label><input id="p-hann" type="checkbox"> Hann window</label><label>Scale<select id="p-scale"><option value="linear">Linear</option><option value="log">Logarithmic</option></select></label><button id="p-run" class="button primary">Calculate</button></div><div id="p-chart" class="popout-chart"></div><div id="p-summary" class="transform-summary">${els.transformSummary.innerHTML}</div>`);
  if (!popup) return;
  popup.document.querySelector("#p-mean").checked=els.transformRemoveMean.checked; popup.document.querySelector("#p-hann").checked=els.transformHann.checked; popup.document.querySelector("#p-scale").value=els.transformScale.value;
  const setMode = mode => { transformMode=mode; els.dftMode.classList.toggle("active",mode==="dft");els.fftMode.classList.toggle("active",mode==="fft"); };
  const refresh=()=>{copyPlot(els.transformChart,popup,"p-chart");popup.document.querySelector("#p-summary").innerHTML=els.transformSummary.innerHTML;};refresh();
  popup.document.querySelector("#p-dft").addEventListener("click",()=>setMode("dft")); popup.document.querySelector("#p-fft").addEventListener("click",()=>setMode("fft"));
  popup.document.querySelector("#p-run").addEventListener("click",()=>{els.transformRemoveMean.checked=popup.document.querySelector("#p-mean").checked;els.transformHann.checked=popup.document.querySelector("#p-hann").checked;els.transformScale.value=popup.document.querySelector("#p-scale").value;calculateTransform();refresh();});
}

function openHdfWindow() {
  if (!state.manifest) return;
  const popup = popupShell("HDF5 File Inspector", `<div class="popout-controls"><label>Find in the complete HDF5 inventory<input id="p-search" type="search" placeholder="Example: DateTimeSaved, serial, pressure"></label><button id="p-clear" class="button ghost" type="button" aria-label="Clear search">× Clear</button><button id="p-find" class="button primary">Find</button><button id="p-prev" class="button ghost">Previous</button><strong id="p-position">0 / 0</strong><button id="p-next" class="button ghost">Next</button><span id="p-count">Enter a search term</span></div><div class="popout-content full-hdf-inventory"><section><h2>Parameters</h2><div id="p-parameters">${els.metadataContent.innerHTML}</div></section><section><h2>Datasets</h2><div id="p-datasets">${els.datasetList.innerHTML}</div></section><section><h2>Data quality</h2><div id="p-quality">${els.qualityContent.innerHTML}</div></section></div>`);
  if (!popup) return;
  let matches=[], index=-1;
  popup.document.querySelectorAll("details").forEach(item => { item.open = true; });
  const fields=[...popup.document.querySelectorAll(".metadata-row,.dataset-card,.quality-item")];
  const focus=step=>{if(!matches.length)return;matches.forEach(node=>node.classList.remove("current-match"));index=(index+step+matches.length)%matches.length;const current=matches[index];current.classList.add("current-match");popup.document.querySelector("#p-position").textContent=`${index+1} / ${matches.length}`;current.scrollIntoView({block:"center",behavior:"smooth"});};
  const clear=()=>{matches.forEach(node=>node.classList.remove("current-match","search-match"));matches=[];index=-1;popup.document.querySelector("#p-search").value="";popup.document.querySelector("#p-position").textContent="0 / 0";popup.document.querySelector("#p-count").textContent="Search cleared";popup.document.querySelector("#p-search").focus();};
  const find=()=>{const q=popup.document.querySelector("#p-search").value.trim().toLocaleLowerCase();matches.forEach(node=>node.classList.remove("current-match","search-match"));if(q.length<2){clear();return;}matches=fields.filter(node=>node.textContent.toLocaleLowerCase().includes(q));matches.forEach(node=>node.classList.add("search-match"));index=matches.length?0:-1;popup.document.querySelector("#p-count").textContent=`${matches.length} matching field${matches.length===1?"":"s"}`;popup.document.querySelector("#p-position").textContent=matches.length?`1 / ${matches.length}`:"0 / 0";if(matches.length){matches[0].classList.add("current-match");matches[0].scrollIntoView({block:"center",behavior:"smooth"});}};
  popup.document.querySelector("#p-find").addEventListener("click",find);popup.document.querySelector("#p-clear").addEventListener("click",clear);popup.document.querySelector("#p-search").addEventListener("keydown",e=>{if(e.key==="Enter")find();});popup.document.querySelector("#p-prev").addEventListener("click",()=>focus(-1));popup.document.querySelector("#p-next").addEventListener("click",()=>focus(1));
}

function bindUi() {
  document.querySelectorAll(".generator-tab").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".generator-tab").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".generator-panel").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      document.querySelector(`#${button.dataset.generatorPanel}`).classList.add("active");
    });
  });
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".tab-button").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      document.querySelector(`#${button.dataset.panel}`).classList.add("active");
    });
  });

  els.fileInput.addEventListener("change", () => uploadFile(els.fileInput.files?.[0]));
  els.companionInput.addEventListener("change", () => addCompanionFiles(els.companionInput.files));
  els.resetApplication.addEventListener("click", resetApplication);
  els.hdfSearchButton.addEventListener("click", searchHdf5);
  els.hdfSearch.addEventListener("keydown", event => { if (event.key === "Enter") { event.preventDefault(); searchHdf5(); } });
  els.hdfSearchPrevious.addEventListener("click", () => focusHdfMatch(-1));
  els.hdfSearchNext.addEventListener("click", () => focusHdfMatch(1));
  els.expandHdf.addEventListener("click", openHdfWindow);
  els.expandSpectrum.addEventListener("click", openSpectrumWindow);
  els.expandEit.addEventListener("click", openEitWindow);
  els.expandTransform.addEventListener("click", openTransformWindow);
  els.loadTimeSeries.addEventListener("click", () => loadTimeSeries(false));
  els.clearTimeRange.addEventListener("click", () => { els.timeMin.value = ""; els.timeMax.value = ""; loadTimeSeries(true); });
  ["dragenter", "dragover"].forEach((eventName) => {
    els.dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      els.dropZone.classList.add("dragging");
    });
  });
  ["dragleave", "drop"].forEach((eventName) => {
    els.dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      els.dropZone.classList.remove("dragging");
    });
  });
  els.dropZone.addEventListener("drop", (event) => uploadFile(event.dataTransfer.files?.[0]));

  els.pathForm.addEventListener("submit", (event) => {
    event.preventDefault();
    openLocalPath(els.pathInput.value.trim());
  });
  els.fixtureButton.addEventListener("click", openFixture);
  els.vocusTargetPicker.addEventListener("change", () => {
    if (els.vocusTargetPicker.value) {
      appendCommaValue(els.vocusTargets, els.vocusTargetPicker.value);
      syncDetectionIdentity(els.vocusTargetPicker.value, 'vocus');
    }
    els.vocusTargetPicker.value = "";
  });
  els.miptofIsotopePicker.addEventListener("change", () => {
    if (els.miptofIsotopePicker.value) {
      appendCommaValue(els.miptofIsotopes, els.miptofIsotopePicker.value);
      syncDetectionIdentity(els.miptofIsotopePicker.value, 'miptof');
    }
    els.miptofIsotopePicker.value = "";
  });
  els.vocusForm.addEventListener("submit", (event) => {
    event.preventDefault();
    generateSynthetic("vocus", {
      reagent: els.vocusReagent.value,
      targets: els.vocusTargets.value,
      environment: els.vocusEnvironment.value,
    });
  });
  els.miptofForm.addEventListener("submit", (event) => {
    event.preventDefault();
    generateSynthetic("miptof", {
      isotopes: els.miptofIsotopes.value,
      environment: els.miptofEnvironment.value,
    });
  });
  els.datasetSearch.addEventListener("input", () => {
    state.datasetQuery = els.datasetSearch.value;
    renderDatasets();
  });
  els.candidateSelect.addEventListener("change", async () => {
    state.candidateId = els.candidateSelect.value;
    state.fullRange = null;
    els.rangeMin.value = "";
    els.rangeMax.value = "";
    updateAggregationControl();
    await loadSpectrum({ preserveFullRange: false });
  });
  els.aggregationSelect.addEventListener("change", async () => {
    await loadSpectrum({ preserveFullRange: false });
  });
  els.scaleSelect.addEventListener("change", () => {
    if (!state.spectrum) return;
    Plotly.relayout(els.chart, { "yaxis.type": els.scaleSelect.value, "yaxis.autorange": true });
  });
  els.applyRange.addEventListener("click", async () => {
    try {
      const { min, max } = rangeValues();
      if (min === null && max === null) {
        throw new Error("Enter at least one range boundary, or use Full spectrum.");
      }
      await loadSpectrum({ xMin: min, xMax: max, preserveFullRange: true });
    } catch (error) {
      toast(error.message, "error");
    }
  });
  els.clearRange.addEventListener("click", async () => {
    els.rangeMin.value = "";
    els.rangeMax.value = "";
    await loadSpectrum({ preserveFullRange: false });
  });
  els.resetView.addEventListener("click", () => {
    if (!state.spectrum) return;
    Plotly.relayout(els.chart, { "xaxis.autorange": true, "yaxis.autorange": true });
  });
  els.dftMode.addEventListener("click", () => {
    transformMode = "dft";
    els.dftMode.classList.add("active");
    els.fftMode.classList.remove("active");
    els.transformRun.textContent = "Calculate direct transform";
  });
  els.fftMode.addEventListener("click", () => {
    transformMode = "fft";
    els.fftMode.classList.add("active");
    els.dftMode.classList.remove("active");
    els.transformRun.textContent = "Calculate FFT";
  });
  els.transformRun.addEventListener("click", calculateTransform);
  els.transformScale.addEventListener("change", () => {
    if (!els.transformChart.classList.contains("hidden")) calculateTransform();
  });
  window.addEventListener("resize", () => {
    if (!els.chart.classList.contains("hidden")) Plotly.Plots.resize(els.chart);
    if (!els.transformChart.classList.contains("hidden")) Plotly.Plots.resize(els.transformChart);
    if (!els.timeSeriesChart.classList.contains("hidden")) Plotly.Plots.resize(els.timeSeriesChart);
  });
}

let guideWindow=null;
function openUserGuide(event){
  if(guideWindow&&!guideWindow.closed){guideWindow.focus();event.preventDefault();return;}
  guideWindow=window.open(event.currentTarget.href,'tofshield-user-guide','popup=yes,width=1100,height=850,resizable=yes,scrollbars=yes');
  if(guideWindow){event.preventDefault();guideWindow.focus();}
}

async function initialize() {
  document.querySelector('.guide-link').addEventListener('click',openUserGuide);
  setupWorkspaceTabs();
  setupDetectionCapability();
  bindUi();
  try {
    state.config = await fetchJson("/api/config");
    setupInstrument(state.config.instrument_fields);
    const roots = state.config.allowed_roots.join(", ");
    els.pathHelp.textContent = `Read-only roots: ${roots}. Browser upload limit: ${state.config.upload_limit_mb.toLocaleString()} MiB.`;
    els.fixtureButton.classList.toggle("hidden", !state.config.fixture_available);
    populateGeneratorCatalog(state.config.generator_catalog || {});
    const simulation=new URLSearchParams(location.search).get('simulate');
    if(['vocus','miptof'].includes(simulation))applyDetectedInstrumentContext({family:simulation,confidence:'New educational simulation',limitations:'No measured acquisition loaded.'});
  } catch (error) {
    toast(`Viewer service unavailable: ${error.message}`, "error");
  }
}

initialize();
