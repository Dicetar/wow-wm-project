const state = {
  schemas: [],
  commands: [],
  activeSchema: null,
  formData: {},
  selectedDraft: null,
  latestJob: null,
  activeSession: null,
  tools: null,
  panelMode: "simple"
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    }
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || response.statusText);
  }
  return payload;
}

function pretty(value) {
  return JSON.stringify(value, null, 2);
}

function setOutput(id, value) {
  $(id).textContent = typeof value === "string" ? value : pretty(value);
}

function getSchema(id) {
  return state.schemas.find((entry) => entry.id === id);
}

function schemaForSelect(selectId) {
  return getSchema($(selectId).value);
}

async function init() {
  initTheme();
  initPanelMode();
  bindTabs();
  bindPanelMode();
  bindEditorTabs();
  bindActions();
  await loadAll();
  setPanelMode(state.panelMode);
}

function currentTheme() {
  const explicit = document.documentElement.getAttribute("data-theme");
  if (explicit) return explicit;
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  try { localStorage.setItem("wm-theme", theme); } catch (e) { /* ignore */ }
  const button = $("themeToggle");
  if (button) button.textContent = theme === "dark" ? "Light" : "Dark";
}

function initTheme() {
  let stored = null;
  try { stored = localStorage.getItem("wm-theme"); } catch (e) { /* ignore */ }
  // Honour a stored choice; otherwise follow the OS preference (CSS @media handles it).
  applyTheme(stored || currentTheme());
}

function toggleTheme() {
  applyTheme(currentTheme() === "dark" ? "light" : "dark");
}

async function loadAll() {
  const [status, catalog, schemas, settings, drafts, readiness, autoplay, tools] = await Promise.all([
    api("/api/status"),
    api("/api/catalog"),
    api("/api/schemas"),
    api("/api/llm/settings"),
    api("/api/drafts"),
    api("/api/wm/readiness"),
    api("/api/wm/autoplay/status"),
    api("/api/wm/tools")
  ]);
  state.commands = catalog.commands;
  state.schemas = schemas.schemas;
  state.activeSession = readiness.active_session || status.active_session || null;
  state.tools = tools;
  renderStatus(status);
  renderWmReadiness(readiness);
  renderAutoplay(autoplay);
  renderConvVerbModes(autoplay.conversational_verb_modes || {});
  renderPendingIntents(autoplay.pending_intents || {});
  renderSimple(status, readiness, autoplay, tools);
  renderSchemaSelects();
  renderCommands();
  renderSettings(settings);
  renderDrafts(drafts.drafts || []);
  syncSessionInputs(state.activeSession);
  selectSchema($("contentSchema").value || state.schemas[0]?.id);
}

function bindTabs() {
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      activateTab(button.dataset.tab);
    });
  });
}

function initPanelMode() {
  try {
    state.panelMode = localStorage.getItem("wm-panel-mode") || "simple";
  } catch (e) {
    state.panelMode = "simple";
  }
}

function bindPanelMode() {
  document.querySelectorAll("[data-panel-mode]").forEach((button) => {
    button.addEventListener("click", () => setPanelMode(button.dataset.panelMode));
  });
}

function setPanelMode(mode) {
  state.panelMode = mode === "advanced" ? "advanced" : "simple";
  try { localStorage.setItem("wm-panel-mode", state.panelMode); } catch (e) { /* ignore */ }
  document.querySelectorAll("[data-panel-mode]").forEach((button) => {
    button.classList.toggle("active", button.dataset.panelMode === state.panelMode);
  });
  document.querySelectorAll(".tab").forEach((button) => {
    const scope = button.dataset.modeScope || "advanced";
    button.hidden = scope !== state.panelMode;
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    const scope = panel.dataset.modeScope || "advanced";
    panel.hidden = scope !== state.panelMode;
  });
  const activeButton = document.querySelector(`.tab.active[data-mode-scope="${state.panelMode}"], .tab.active:not([data-mode-scope])`);
  if (!activeButton || activeButton.hidden) {
    const first = document.querySelector(`.tab[data-mode-scope="${state.panelMode}"]:not([hidden])`);
    if (first) activateTab(first.dataset.tab);
  }
}

function activateTab(tabId) {
  document.querySelectorAll(".tab, .tab-panel").forEach((item) => item.classList.remove("active"));
  const button = Array.from(document.querySelectorAll(".tab")).find((item) => item.dataset.tab === tabId);
  const panel = $(tabId);
  if (button) button.classList.add("active");
  if (panel) panel.classList.add("active");
}

function bindEditorTabs() {
  document.querySelectorAll(".subtab").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".subtab, .editor-tab").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      $(`editor${capitalize(button.dataset.editorTab)}`).classList.add("active");
    });
  });
}

function bindActions() {
  $("themeToggle").addEventListener("click", toggleTheme);
  $("refreshAll").addEventListener("click", loadAll);
  $("saveLlmSettings").addEventListener("click", saveLlmSettings);
  $("fetchModels").addEventListener("click", fetchModels);
  $("generateDraft").addEventListener("click", generateDraft);
  $("contentSchema").addEventListener("change", (event) => selectSchema(event.target.value));
  $("resetSchemaForm").addEventListener("click", () => selectSchema($("contentSchema").value));
  $("validateSchemaPayload").addEventListener("click", validateEditorPayload);
  $("planSchemaPayload").addEventListener("click", () => runPayloadCommand("content.release.plan", "validationResult"));
  $("packetSchemaPayload").addEventListener("click", () => runPayloadCommand("content.release.packet", "validationResult"));
  $("adoptDraft").addEventListener("click", adoptSelectedDraft);
  $("rejectDraft").addEventListener("click", rejectSelectedDraft);
  $("dryRunDraft").addEventListener("click", dryRunSelectedDraft);
  $("confirmApply").addEventListener("click", confirmApply);
  document.querySelectorAll("[data-release-command]").forEach((button) => {
    button.addEventListener("click", () => runPayloadCommand(button.dataset.releaseCommand, "releaseOutput"));
  });
  $("sliceBootstrap").addEventListener("click", sliceBootstrap);
  $("slicePoll").addEventListener("click", slicePoll);
  $("sliceRefresh").addEventListener("click", refreshSlice);
  $("autoplaySaveConfig").addEventListener("click", configureAutoplay);
  $("convVerbModesSave").addEventListener("click", saveConvVerbModes);
  $("pendingIntentsList").addEventListener("click", onPendingListClick);
  $("simplePendingIntentsList").addEventListener("click", onPendingListClick);
  $("autoplayGenerate").addEventListener("click", generateAutoplayOnce);
  $("autoplayPause").addEventListener("click", () => setAutoplayPaused(true));
  $("autoplayResume").addEventListener("click", () => setAutoplayPaused(false));
  $("autoplayResetChatContext").addEventListener("click", resetChatContext);
  $("scanMarkers").addEventListener("click", scanMarkers);
  $("inboxKindFilter").addEventListener("change", refreshSlice);
  $("rollbackArtifact").addEventListener("click", sliceRollback);
  $("simpleRefresh").addEventListener("click", loadAll);
  $("simplePause").addEventListener("click", () => setAutoplayPaused(true));
  $("simpleResume").addEventListener("click", () => setAutoplayPaused(false));
  $("simplePublishLane").addEventListener("change", renderSchemaSelects);
  $("simplePublishSchema").addEventListener("change", (event) => selectSchema(event.target.value));
  $("simpleValidate").addEventListener("click", simpleValidateSelected);
  $("simpleDryRun").addEventListener("click", simpleRunSelected);
  $("simpleOpenAdvanced").addEventListener("click", () => {
    setPanelMode("advanced");
    activateTab("content");
  });
  $("simpleSaveLlm").addEventListener("click", simpleSaveLlmSettings);
  $("simpleFetchModels").addEventListener("click", simpleFetchModels);
  $("simpleGenerateOnce").addEventListener("click", simpleGenerateAutoplayOnce);
  $("simpleResetChatContext").addEventListener("click", simpleResetChatContext);
  $("simpleAdoptDraft").addEventListener("click", adoptSelectedDraft);
  $("simpleRejectDraft").addEventListener("click", rejectSelectedDraft);
  $("simpleDryRunDraft").addEventListener("click", dryRunSelectedDraft);
  $("simpleRollback").addEventListener("click", simpleRollback);
}

function renderStatus(status) {
  $("statusLine").textContent = `${status.status} | schemas ${status.schema_count} | commands ${status.command_count}`;
  const rows = {
    "Panel": status.panel,
    "State Root": status.state_root,
    "Git Dirty": status.git?.dirty,
    "LM Studio": status.llm?.base_url,
    "Model": status.llm?.model || "(not selected)"
  };
  $("overviewStatus").innerHTML = Object.entries(rows)
    .map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(String(value))}</dd>`)
    .join("");
  setOutput("latestJob", status.latest_job || {});
}

function renderSimple(status, readiness, autoplay, tools) {
  const session = readiness.active_session || state.activeSession || {};
  const llm = autoplay.llm || {};
  const config = autoplay.config || {};
  const blockers = readiness.apply_blockers || [];
  const rows = {
    "Character": session.character_guid ? `${session.character_guid}${session.character_name ? ` / ${session.character_name}` : ""}` : "(none)",
    "Readiness": readiness.can_apply === false ? "blocked" : "ready",
    "Autoplay": autoplay.running ? (autoplay.paused ? "paused" : "running") : "stopped",
    "LLM": llm.ok ? (llm.model || "ready") : (llm.error || "not ready"),
    "Chat Context": `epoch ${config.llm_chat_context_epoch || 0}`,
    "Lanes": (config.llm_lanes || []).join(",") || "(none)",
    "Latest": autoplay.latest_opportunity?.source_event_key || autoplay.latest_autoplay?.status || "(none)"
  };
  $("simpleStatus").innerHTML = Object.entries(rows)
    .map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(String(value))}</dd>`)
    .join("");
  $("simpleBlockers").innerHTML = blockers.length
    ? blockers.map((blocker) => `<div class="card">${escapeHtml(blocker.check || "blocker")}: ${escapeHtml(blocker.status || "")}</div>`).join("")
    : `<div class="card">Ready</div>`;
  setOutput("simpleActivity", {
    latest_opportunity: autoplay.latest_opportunity || null,
    latest_proposal: autoplay.latest_proposal || null,
    latest_apply: autoplay.latest_autoplay || autoplay.latest_apply || null,
    latest_job: status.latest_job || null,
  });
  const nativeActions = Array.isArray(tools.native_actions) ? tools.native_actions.length : 0;
  $("simpleTools").innerHTML = Object.entries({
    "Input": tools.player_input?.preferred || "WM chat channel",
    "Output": tools.player_output?.preferred_action || "player_chat_message",
    "Native Actions": nativeActions,
    "Draft Contract": tools.model_contract || "typed drafts only"
  }).map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(String(value))}</dd>`).join("");
  if (session.character_guid) $("simpleCharacterGuid").value = session.character_guid;
  const verbModes = autoplay.conversational_verb_modes || {};
  const verbValues = Object.values(verbModes);
  const nAuto = verbValues.filter((m) => m === "auto").length;
  const nConfirm = verbValues.filter((m) => m === "confirm").length;
  const nOff = verbValues.filter((m) => m === "off").length;
  const summaryEl = $("simpleConvVerbSummary");
  if (summaryEl) {
    summaryEl.textContent = verbValues.length
      ? `${nAuto} auto, ${nConfirm} confirm, ${nOff} off`
      : "—";
  }
}

function renderSchemaSelects() {
  const lane = $("simplePublishLane")?.value || "";
  const filtered = lane ? state.schemas.filter((schema) => String(schema.id).includes(`.${lane}.`) || String(schema.id).includes(`${lane}.`) || (lane === "action" && schema.id === "control.proposal.v1")) : state.schemas;
  const options = state.schemas.map((schema) => `<option value="${escapeHtml(schema.id)}">${escapeHtml(schema.label)}</option>`).join("");
  const simpleOptions = (filtered.length ? filtered : state.schemas).map((schema) => `<option value="${escapeHtml(schema.id)}">${escapeHtml(schema.label)}</option>`).join("");
  ["llmSchema", "contentSchema"].forEach((id) => {
    const current = $(id).value;
    $(id).innerHTML = options;
    if (current) $(id).value = current;
  });
  const simple = $("simplePublishSchema");
  if (simple) {
    const current = simple.value;
    simple.innerHTML = simpleOptions;
    if (current && Array.from(simple.options).some((option) => option.value === current)) simple.value = current;
  }
}

function renderCommands() {
  renderCommandGroup("watcherCommands", ["watcher.status", "watcher.start", "watcher.stop", "bridge_lab.start"]);
  renderCommandGroup("nativeCommands", ["native.queue.inspect", "native.queue.recover", "native.queue.cleanup"], () => {
    const guid = activeSessionGuid();
    const params = { limit: Number($("watcherLimit").value || 20) };
    if (guid) params.player_guid = guid;
    return params;
  });
  renderCommandGroup("markerCommands", ["marker.scan", "marker.scope_latest", "marker.observe_all.start", "marker.observe_all.stop"], () => ({
    marker_spell_id: Number($("markerSpellId").value || 946602),
    since_seconds: Number($("markerSinceSeconds").value || 300),
    expires_seconds: 900,
    limit: 20
  }));
  renderCommandGroup("maintenanceCommands", ["items.rollback", "quests.purge_range"], (commandId) => {
    if (commandId === "items.rollback") return { item_entry: Number($("rollbackItemEntry").value || 0) };
    return { quest_id: Number($("purgeQuestId").value || 0) };
  });
}

function renderCommandGroup(containerId, commandIds, paramsFactory = () => ({})) {
  $(containerId).innerHTML = commandIds.map((id) => {
    const command = state.commands.find((entry) => entry.id === id);
    if (!command) return "";
    return `<button data-command-id="${escapeHtml(id)}">${escapeHtml(command.label)}</button>`;
  }).join("");
  $(containerId).querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => runCommand(button.dataset.commandId, paramsFactory(button.dataset.commandId), null, "jobOutput"));
  });
}

function renderSettings(settings) {
  $("llmBaseUrl").value = settings.base_url || "http://localhost:1234/v1";
  $("llmTemperature").value = settings.temperature ?? 0.2;
  $("llmTopP").value = settings.top_p ?? "";
  $("llmMaxTokens").value = settings.max_tokens ?? 2048;
  $("llmTimeout").value = settings.timeout_seconds ?? 60;
  $("llmSchemaMode").value = settings.schema_mode || "json_schema";
  $("simpleLlmBaseUrl").value = settings.base_url || "http://localhost:1234/v1";
  $("simpleLlmTemperature").value = settings.temperature ?? 0.2;
  $("simpleLlmTopP").value = settings.top_p ?? "";
  $("simpleLlmMaxTokens").value = settings.max_tokens ?? 2048;
  renderModelSelect(settings.model ? [settings.model] : [], settings.model);
}

function renderWmReadiness(readiness) {
  const doctor = readiness.doctor || {};
  const failed = (doctor.checks || []).filter((check) => check.status === "FAIL").length;
  const unknown = (doctor.checks || []).filter((check) => check.status === "UNKNOWN").length;
  const session = readiness.active_session || null;
  const profile = readiness.operator_profile || {};
  const blockers = readiness.apply_blockers || [];
  const rows = {
    "Readiness": readiness.can_apply === false ? "PARTIAL" : "WORKING",
    "Doctor": `${failed} FAIL, ${unknown} UNKNOWN`,
    "Profile": profile.profile || "(unknown)",
    "World DB": profile.world_db ? `${profile.world_db.host}:${profile.world_db.port}/${profile.world_db.name}` : "(unknown)",
    "SOAP": profile.soap ? `${profile.soap.host}:${profile.soap.port}` : "(unknown)",
    "Cannot Apply Because": blockers.length ? blockers.map((b) => `${b.check}: ${b.status}`).join("; ") : "ready",
    "Marker Spell": readiness.marker_spell_id,
    "Selected": session ? `${session.character_guid}${session.character_name ? ` / ${session.character_name}` : ""}` : "(none)",
    "Source": session?.source || "(none)"
  };
  $("wmReadiness").innerHTML = Object.entries(rows)
    .map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(String(value))}</dd>`)
    .join("");
}

function renderAutoplay(autoplay) {
  const llm = autoplay.llm || {};
  const readiness = autoplay.readiness || {};
  const counters = autoplay.counters || {};
  const config = autoplay.config || {};
  const rows = {
    "Status": autoplay.status || "(unknown)",
    "Running": autoplay.running ? "yes" : "no",
    "Paused": autoplay.paused ? "yes" : "no",
    "Readiness": readiness.ok ? "ready" : "blocked",
    "LLM": llm.ok ? `${llm.model || "(model)"}` : (llm.error || "not ready"),
    "WM Chat": config.llm_chat_enabled === false ? "off" : "on",
    "Chat Context": `epoch ${config.llm_chat_context_epoch || 0}`,
    "Last Forget": config.llm_chat_context_reset_at || "(never)",
    "Lanes": (config.llm_lanes || []).join(",") || "(none)",
    "Drafts": counters.drafts_generated || 0,
    "Auto Applied": counters.auto_applied || 0,
    "Ticks": counters.ticks || 0,
    "Issues": (autoplay.issues || []).length,
    "Maintenance": (autoplay.maintenance_pending || []).length,
    "Latest Event": autoplay.latest_opportunity?.source_event_key || "(none)",
    "Latest Draft": autoplay.latest_proposal?.draft_id || "(none)",
    "Latest Apply": autoplay.latest_autoplay?.status || autoplay.latest_apply?.status || "(none)"
  };
  $("autoplayStatus").innerHTML = Object.entries(rows)
    .map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(String(value))}</dd>`)
    .join("");
  $("autoplayLlmEnabled").checked = config.llm_enabled !== false;
  $("autoplayLanes").value = (config.llm_lanes || ["chat", "scene", "action"]).join(",");
  $("autoplayModel").value = config.llm_model || llm.model || $("llmModel")?.value || "";
  $("simpleLlmLanes").value = (config.llm_lanes || ["chat"]).join(",");
  $("simpleLlmModel").value = config.llm_model || llm.model || $("llmModel")?.value || "";
  $("autoplayEventAgeSeconds").value = config.llm_event_age_seconds ?? 300;
  $("autoplayCooldownSeconds").value = config.llm_cooldown_seconds ?? 60;
  $("autoplayEventsPerTick").value = config.llm_events_per_tick ?? 1;
}

function autoplayConfigPayload() {
  return {
    llm_enabled: $("autoplayLlmEnabled").checked,
    llm_chat_enabled: true,
    llm_lanes: $("autoplayLanes").value.split(",").map((item) => item.trim()).filter(Boolean),
    llm_model: $("autoplayModel").value || $("llmModel").value || null,
    llm_base_url: $("llmBaseUrl").value || null,
    llm_event_age_seconds: Number($("autoplayEventAgeSeconds").value || 300),
    llm_cooldown_seconds: Number($("autoplayCooldownSeconds").value || 60),
    llm_events_per_tick: Number($("autoplayEventsPerTick").value || 1)
  };
}

async function configureAutoplay() {
  const result = await api("/api/wm/autoplay/configure", {
    method: "POST",
    body: JSON.stringify(autoplayConfigPayload())
  });
  renderAutoplay(result.autoplay || {});
  setOutput("autoplayOutput", result);
}

function renderConvVerbModes(modes) {
  state.convVerbModes = { ...(modes || {}) };
  const list = $("convVerbModesList");
  const empty = $("convVerbModesEmpty");
  const actions = $("convVerbModesActions");
  if (!list) return;
  const meta = {};
  (state.tools?.native_actions || []).forEach((action) => { meta[action.kind] = action; });
  const entries = Object.entries(state.convVerbModes).sort(([a], [b]) => a.localeCompare(b));
  if (!entries.length) {
    list.hidden = true;
    list.innerHTML = "";
    if (actions) actions.hidden = true;
    if (empty) { empty.hidden = false; empty.textContent = "No conversational verbs available."; }
    return;
  }
  if (empty) empty.hidden = true;
  list.hidden = false;
  if (actions) actions.hidden = false;
  const option = (mode, value, label) => `<option value="${value}"${value === mode ? " selected" : ""}>${label}</option>`;
  list.innerHTML = entries.map(([verb, mode]) => {
    const info = meta[verb] || {};
    const risk = info.risk ? ` <span class="muted small">risk: ${escapeHtml(String(info.risk))}</span>` : "";
    const desc = info.description ? `<div class="muted small">${escapeHtml(String(info.description))}</div>` : "";
    return `<div class="card verb-mode-row">
      <div class="verb-mode-head">
        <code>${escapeHtml(verb)}</code>${risk}
        <select data-verb-mode="${escapeHtml(verb)}">${option(mode, "off", "Off")}${option(mode, "confirm", "Confirm")}${option(mode, "auto", "Auto")}</select>
      </div>${desc}
    </div>`;
  }).join("");
}

async function saveConvVerbModes() {
  const modes = {};
  document.querySelectorAll("[data-verb-mode]").forEach((select) => {
    modes[select.dataset.verbMode] = select.value;
  });
  try {
    const result = await api("/api/wm/autoplay/configure", {
      method: "POST",
      body: JSON.stringify({ conversational_verb_modes: modes })
    });
    setOutput("autoplayOutput", result);
    const saved = $("convVerbModesSaved");
    if (saved) { saved.hidden = false; setTimeout(() => { saved.hidden = true; }, 2000); }
    await loadAll();
  } catch (error) {
    setOutput("autoplayOutput", { ok: false, error: error.message });
  }
}

function pendingIntentCards(pending) {
  const now = Date.now();
  return Object.entries(pending || {})
    .map(([guid, record]) => ({ guid, record: record || {} }))
    .filter(({ record }) => {
      if (!record.expires_at) return true;
      const expires = Date.parse(record.expires_at);
      return Number.isNaN(expires) || expires > now;
    });
}

function renderPendingIntents(pending) {
  const cards = pendingIntentCards(pending);
  const html = cards.map(({ guid, record }) => {
    const verb = escapeHtml(String(record.verb || "action").replaceAll("_", " "));
    const risk = record.risk ? `<span class="muted small">risk: ${escapeHtml(String(record.risk))}</span>` : "";
    const summary = record.summary ? `<div class="muted small">${escapeHtml(String(record.summary))}</div>` : "";
    const expires = record.expires_at ? `<div class="muted small">expires ${escapeHtml(String(record.expires_at))}</div>` : "";
    return `<div class="card pending-intent">
      <div class="pending-intent-head"><strong>${verb}</strong> ${risk} <span class="muted small">guid ${escapeHtml(String(guid))}</span></div>
      ${summary}${expires}
      <div class="button-row">
        <button class="primary" data-intent-approve="${escapeHtml(String(guid))}">Approve</button>
        <button class="danger" data-intent-reject="${escapeHtml(String(guid))}">Reject</button>
      </div>
    </div>`;
  }).join("");
  [["pendingIntentsList", "pendingIntentsEmpty"], ["simplePendingIntentsList", "simplePendingIntentsEmpty"]].forEach(([listId, emptyId]) => {
    const list = $(listId);
    const empty = $(emptyId);
    if (!list) return;
    if (cards.length) {
      list.hidden = false;
      list.innerHTML = html;
      if (empty) empty.hidden = true;
    } else {
      list.hidden = true;
      list.innerHTML = "";
      if (empty) empty.hidden = false;
    }
  });
}

async function resolveIntent(path, guid) {
  try {
    const result = await api(path, {
      method: "POST",
      body: JSON.stringify({ player_guid: Number(guid) })
    });
    setOutput("autoplayOutput", result);
  } catch (error) {
    setOutput("autoplayOutput", { ok: false, error: error.message });
  }
  await loadAll();
}

function onPendingListClick(event) {
  const approve = event.target.closest("[data-intent-approve]");
  if (approve) { resolveIntent("/api/wm/autoplay/intent/approve", approve.dataset.intentApprove); return; }
  const reject = event.target.closest("[data-intent-reject]");
  if (reject) { resolveIntent("/api/wm/autoplay/intent/reject", reject.dataset.intentReject); }
}

async function generateAutoplayOnce() {
  const guid = activeSessionGuid();
  if (!guid) {
    setOutput("autoplayOutput", { ok: false, error: "Select or bootstrap a session character first." });
    return;
  }
  await configureAutoplay();
  const lanes = autoplayConfigPayload().llm_lanes;
  const result = await api("/api/wm/autoplay/generate", {
    method: "POST",
    body: JSON.stringify({
      player_guid: guid,
      lane: lanes[0] || "scene",
      llm_model: $("autoplayModel").value || $("llmModel").value || null,
      llm_base_url: $("llmBaseUrl").value || null
    })
  });
  setOutput("autoplayOutput", result);
  await refreshDrafts();
  await loadAll();
}

async function setAutoplayPaused(paused) {
  const result = await api(paused ? "/api/wm/autoplay/pause" : "/api/wm/autoplay/resume", {
    method: "POST",
    body: "{}"
  });
  renderAutoplay(result.autoplay || {});
}

async function resetChatContext() {
  const guid = activeSessionGuid();
  const result = await api("/api/wm/autoplay/reset-chat-context", {
    method: "POST",
    body: JSON.stringify({ actor_guid: guid || null })
  });
  renderAutoplay(result.autoplay || {});
  setOutput("autoplayOutput", result);
  return result;
}

function renderModelSelect(models, selected) {
  const unique = Array.from(new Set(models.filter(Boolean)));
  if (selected && !unique.includes(selected)) unique.unshift(selected);
  const html = [
    `<option value="">Select model</option>`,
    ...unique.map((model) => `<option value="${escapeHtml(model)}">${escapeHtml(model)}</option>`)
  ].join("");
  $("llmModel").innerHTML = html;
  $("simpleLlmModel").innerHTML = html;
  if (selected) $("llmModel").value = selected;
  if (selected) $("simpleLlmModel").value = selected;
}

function currentLlmSettings() {
  return {
    base_url: $("llmBaseUrl").value,
    model: $("llmModel").value || null,
    temperature: Number($("llmTemperature").value || 0.2),
    top_p: $("llmTopP").value === "" ? null : Number($("llmTopP").value),
    max_tokens: Number($("llmMaxTokens").value || 2048),
    timeout_seconds: Number($("llmTimeout").value || 60),
    schema_mode: $("llmSchemaMode").value,
    api_key: $("llmApiKey").value || null
  };
}

function syncSimpleLlmToAdvanced() {
  $("llmBaseUrl").value = $("simpleLlmBaseUrl").value || "http://localhost:1234/v1";
  $("llmModel").value = $("simpleLlmModel").value || "";
  $("llmTemperature").value = $("simpleLlmTemperature").value || 0.2;
  $("llmTopP").value = $("simpleLlmTopP").value || "";
  $("llmMaxTokens").value = $("simpleLlmMaxTokens").value || 2048;
  $("autoplayModel").value = $("simpleLlmModel").value || "";
  $("autoplayLanes").value = $("simpleLlmLanes").value || "chat";
}

async function simpleSaveLlmSettings() {
  syncSimpleLlmToAdvanced();
  const settings = await api("/api/llm/settings", { method: "POST", body: JSON.stringify(currentLlmSettings()) });
  const autoplay = await api("/api/wm/autoplay/configure", { method: "POST", body: JSON.stringify(autoplayConfigPayload()) });
  setOutput("simpleLlmOutput", { settings, autoplay });
}

async function simpleFetchModels() {
  syncSimpleLlmToAdvanced();
  await saveLlmSettings();
  const result = await api("/api/llm/models");
  renderModelSelect(result.models || [], $("simpleLlmModel").value || $("llmModel").value);
  setOutput("simpleLlmOutput", result);
}

async function simpleGenerateAutoplayOnce() {
  syncSimpleLlmToAdvanced();
  await generateAutoplayOnce();
  $("simpleLlmOutput").textContent = $("autoplayOutput").textContent;
}

async function simpleResetChatContext() {
  const result = await resetChatContext();
  setOutput("simpleLlmOutput", result);
}

async function saveLlmSettings() {
  const result = await api("/api/llm/settings", { method: "POST", body: JSON.stringify(currentLlmSettings()) });
  if (result.autoplay) renderAutoplay(result.autoplay);
  setOutput("llmResult", result);
}

async function fetchModels() {
  await saveLlmSettings();
  const result = await api("/api/llm/models");
  renderModelSelect(result.models || [], $("llmModel").value);
  setOutput("llmResult", result);
}

async function generateDraft() {
  const result = await api("/api/llm/generate", {
    method: "POST",
    body: JSON.stringify({
      schema_version: $("llmSchema").value,
      instruction: $("llmInstruction").value,
      context_pack_path: $("llmContextPath").value || null,
      candidate_pack_path: $("llmCandidatePath").value || null,
      settings: currentLlmSettings()
    })
  });
  setOutput("llmResult", result);
  await refreshDrafts();
}

async function simpleValidateSelected() {
  const schemaId = $("simplePublishSchema").value;
  if (schemaId) selectSchema(schemaId);
  const payload = payloadFromEditor();
  const result = await api("/api/schema/validate", {
    method: "POST",
    body: JSON.stringify({ schema_version: state.activeSchema.id, payload })
  });
  setOutput("simplePublishOutput", result);
}

async function simpleRunSelected() {
  const schemaId = $("simplePublishSchema").value;
  if (schemaId) selectSchema(schemaId);
  const result = await runPayloadCommand($("simplePublishCommand").value, "simplePublishOutput");
  setOutput("simplePublishOutput", result);
}

function selectSchema(schemaId) {
  state.activeSchema = getSchema(schemaId);
  if (!state.activeSchema) return;
  state.formData = defaultValue(state.activeSchema.schema);
  syncRawFromForm();
  renderEditorForm();
  setOutput("validationResult", {});
}

function defaultValue(schema) {
  if (!schema || typeof schema !== "object") return null;
  if (Object.prototype.hasOwnProperty.call(schema, "default")) return clone(schema.default);
  if (Object.prototype.hasOwnProperty.call(schema, "const")) return clone(schema.const);
  if (schema.enum && schema.enum.length) return clone(schema.enum[0]);
  const type = Array.isArray(schema.type) ? schema.type.find((item) => item !== "null") : schema.type;
  if (type === "object") {
    const result = {};
    const properties = schema.properties || {};
    Object.keys(properties).forEach((key) => {
      if ((schema.required || []).includes(key) || Object.prototype.hasOwnProperty.call(properties[key], "default") || Object.prototype.hasOwnProperty.call(properties[key], "const")) {
        result[key] = defaultValue(properties[key]);
      }
    });
    return result;
  }
  if (type === "array") return [];
  if (type === "integer" || type === "number") return 0;
  if (type === "boolean") return false;
  if (type === "string") return "";
  return null;
}

function renderEditorForm() {
  $("editorForm").innerHTML = "";
  $("editorForm").appendChild(renderField(state.activeSchema.schema, state.formData, []));
}

function renderField(schema, value, path) {
  const type = schemaType(schema);
  if (type === "object") return renderObject(schema, value || {}, path);
  if (type === "array") return renderArray(schema, value || [], path);
  return renderScalar(schema, value, path);
}

function renderObject(schema, value, path) {
  const fieldset = document.createElement("fieldset");
  const legend = document.createElement("legend");
  legend.textContent = path.length ? humanize(path[path.length - 1]) : state.activeSchema.label;
  fieldset.appendChild(legend);
  const properties = schema.properties || {};
  const localOrder = schema["ui:order"] || schema.ui?.order;
  const order = localOrder || (path.length === 0 ? state.activeSchema.ui?.order : null) || Object.keys(properties);
  const keys = [...order.filter((key) => properties[key]), ...Object.keys(properties).filter((key) => !order.includes(key))];
  keys.forEach((key) => {
    if (!Object.prototype.hasOwnProperty.call(value, key)) value[key] = defaultValue(properties[key]);
    fieldset.appendChild(renderField(properties[key], value[key], [...path, key]));
  });
  return fieldset;
}

function renderArray(schema, value, path) {
  const wrapper = document.createElement("fieldset");
  const legend = document.createElement("legend");
  legend.textContent = path[path.length - 1] || "items";
  wrapper.appendChild(legend);
  value.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = "array-row";
    row.appendChild(renderField(schema.items || { type: "string" }, item, [...path, index]));
    const remove = document.createElement("button");
    remove.textContent = "Remove";
    remove.addEventListener("click", () => {
      value.splice(index, 1);
      syncRawFromForm();
      renderEditorForm();
    });
    row.appendChild(remove);
    wrapper.appendChild(row);
  });
  const add = document.createElement("button");
  add.textContent = "Add";
  add.addEventListener("click", () => {
    value.push(defaultValue(schema.items || { type: "string" }));
    syncRawFromForm();
    renderEditorForm();
  });
  wrapper.appendChild(add);
  return wrapper;
}

function renderScalar(schema, value, path) {
  const label = document.createElement("label");
  const title = document.createElement("span");
  title.textContent = humanize(path[path.length - 1] || "value");
  let input;
  if (schema.enum) {
    input = document.createElement("select");
    const labels = Array.isArray(schema["ui:enumNames"]) ? schema["ui:enumNames"] : [];
    schema.enum.forEach((choice, index) => {
      const option = document.createElement("option");
      option.value = optionValue(choice);
      option.textContent = labels[index] || displayValue(choice);
      input.appendChild(option);
    });
  } else if (schema["ui:widget"] === "textarea") {
    input = document.createElement("textarea");
    input.rows = 4;
  } else {
    input = document.createElement("input");
    if (schemaType(schema) === "integer" || schemaType(schema) === "number") input.type = "number";
    if (schemaType(schema) === "boolean") input.type = "checkbox";
    if (Array.isArray(schema["ui:suggestions"])) {
      const listId = `suggestions-${path.map((part) => String(part).replace(/[^a-zA-Z0-9_-]/g, "-")).join("-")}`;
      input.setAttribute("list", listId);
      const datalist = document.createElement("datalist");
      datalist.id = listId;
      const suggestionLabels = Array.isArray(schema["ui:suggestionLabels"]) ? schema["ui:suggestionLabels"] : [];
      schema["ui:suggestions"].forEach((choice, index) => {
        const option = document.createElement("option");
        option.value = displayValue(choice);
        if (suggestionLabels[index]) option.label = suggestionLabels[index];
        datalist.appendChild(option);
      });
      label.appendChild(datalist);
    }
  }
  if (input.type === "checkbox") {
    input.checked = Boolean(value);
  } else if (schema.enum) {
    input.value = optionValue(value);
  } else {
    input.value = value === null || value === undefined ? "" : value;
  }
  if (Object.prototype.hasOwnProperty.call(schema, "const")) {
    input.readOnly = true;
    if (input.type === "checkbox" || input.tagName === "SELECT") input.disabled = true;
  }
  input.addEventListener("input", () => {
    setAtPath(state.formData, path, readInputValue(input, schema));
    syncRawFromForm();
  });
  input.addEventListener("change", () => {
    setAtPath(state.formData, path, readInputValue(input, schema));
    syncRawFromForm();
  });
  if (input.type === "checkbox") {
    label.className = "checkbox-label";
    label.appendChild(input);
    label.appendChild(title);
  } else {
    label.appendChild(title);
    label.appendChild(input);
  }
  return label;
}

function readInputValue(input, schema) {
  const type = schemaType(schema);
  if (input.tagName === "SELECT" && schema.enum) return valueFromOption(input.value, schema);
  if (type === "boolean") return input.checked;
  if (type === "integer") return input.value === "" ? null : Number.parseInt(input.value, 10);
  if (type === "number") return input.value === "" ? null : Number.parseFloat(input.value);
  return input.value === "" && Array.isArray(schema.type) && schema.type.includes("null") ? null : input.value;
}

function syncRawFromForm() {
  $("rawJson").value = pretty(state.formData);
}

function payloadFromEditor() {
  try {
    state.formData = JSON.parse($("rawJson").value || "{}");
    renderEditorForm();
    return state.formData;
  } catch (error) {
    setOutput("validationResult", { ok: false, error: error.message });
    throw error;
  }
}

async function validateEditorPayload() {
  const payload = payloadFromEditor();
  const result = await api("/api/schema/validate", {
    method: "POST",
    body: JSON.stringify({ schema_version: state.activeSchema.id, payload })
  });
  setOutput("validationResult", result);
  return result;
}

async function runPayloadCommand(commandId, outputId) {
  const payload = payloadFromEditor();
  const result = await runCommand(commandId, {}, payload, outputId);
  $("confirmJobId").value = result.job_id || "";
  $("confirmText").value = "";
  return result;
}

async function runCommand(commandId, params, payload, outputId) {
  const result = await api("/api/jobs/dry-run", {
    method: "POST",
    body: JSON.stringify({ command_id: commandId, params, payload })
  });
  state.latestJob = result;
  setOutput(outputId, result);
  setOutput("jobOutput", result);
  return result;
}

async function confirmApply() {
  const result = await api("/api/jobs/apply", {
    method: "POST",
    body: JSON.stringify({ job_id: $("confirmJobId").value, confirmation: $("confirmText").value })
  });
  state.latestJob = result;
  setOutput("releaseOutput", result);
  setOutput("jobOutput", result);
}

async function refreshDrafts() {
  const drafts = await api("/api/drafts");
  renderDrafts(drafts.drafts || []);
}

function renderDrafts(drafts) {
  const html = drafts.map((draft) => {
    const label = `${draft.created_at || ""} | ${draft.origin} | ${draft.schema_version} | ${draft.state}`;
    return `<button data-draft-id="${escapeHtml(draft.draft_id)}">${escapeHtml(label)}</button>`;
  }).join("");
  $("draftList").innerHTML = html;
  $("simpleDraftList").innerHTML = html;
  document.querySelectorAll("#draftList button, #simpleDraftList button").forEach((button) => {
    button.addEventListener("click", async () => {
      state.selectedDraft = await api(`/api/drafts/${encodeURIComponent(button.dataset.draftId)}`);
      setDraftOutput(state.selectedDraft);
    });
  });
}

function setDraftOutput(value) {
  setOutput("draftDetail", value);
  setOutput("simpleDraftDetail", value);
}

async function adoptSelectedDraft() {
  if (!state.selectedDraft) return;
  const adopted = await api(`/api/drafts/${encodeURIComponent(state.selectedDraft.draft_id)}/adopt`, {
    method: "POST",
    body: JSON.stringify({ operator_name: "operator-reviewed" })
  });
  state.selectedDraft = adopted;
  setDraftOutput(adopted);
  await refreshDrafts();
}

async function rejectSelectedDraft() {
  if (!state.selectedDraft) return;
  const rejected = await api(`/api/drafts/${encodeURIComponent(state.selectedDraft.draft_id)}/reject`, {
    method: "POST",
    body: JSON.stringify({})
  });
  state.selectedDraft = rejected;
  setDraftOutput(rejected);
  await refreshDrafts();
}

async function dryRunSelectedDraft() {
  if (!state.selectedDraft || !state.selectedDraft.parsed_json) return;
  if (state.selectedDraft.origin !== "human_reviewed") {
    setDraftOutput({
      ok: false,
      error: "Adopt the draft as reviewed before dry-run. LLM drafts never run directly.",
      draft: state.selectedDraft
    });
    return;
  }
  const schemaVersion = state.selectedDraft.schema_version;
  const commandId = schemaVersion === "control.proposal.v1" ? "control.apply" : "content.release.plan";
  const result = await runCommand(commandId, {}, state.selectedDraft.parsed_json, "draftDetail");
  setOutput("simpleDraftDetail", result);
}

function activeSessionGuid() {
  const raw = $("watcherPlayerGuid").value || $("sliceCharacterGuid").value || state.activeSession?.character_guid;
  const parsed = Number(raw || 0);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function syncSessionInputs(session) {
  if (!session || !session.character_guid) return;
  $("sliceCharacterGuid").value = session.character_guid;
  $("watcherPlayerGuid").value = session.character_guid;
  if (session.marker_spell_id) $("markerSpellId").value = session.marker_spell_id;
}

function schemaType(schema) {
  if (!schema) return "string";
  const type = schema.type;
  if (Array.isArray(type)) return type.find((item) => item !== "null") || "string";
  return type || "string";
}

function setAtPath(target, path, value) {
  let cursor = target;
  for (let index = 0; index < path.length - 1; index += 1) {
    cursor = cursor[path[index]];
  }
  cursor[path[path.length - 1]] = value;
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function humanize(value) {
  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function displayValue(value) {
  if (value === null) return "";
  if (value === undefined) return "";
  return String(value);
}

function optionValue(value) {
  if (value === null) return "__WM_NULL__";
  if (value === true) return "__WM_TRUE__";
  if (value === false) return "__WM_FALSE__";
  return String(value);
}

function valueFromOption(encoded, schema) {
  const choices = schema.enum || [];
  for (const choice of choices) {
    if (optionValue(choice) === encoded) return clone(choice);
  }
  const type = schemaType(schema);
  if (type === "integer") return Number.parseInt(encoded, 10);
  if (type === "number") return Number.parseFloat(encoded);
  if (type === "boolean") return encoded === "__WM_TRUE__";
  return encoded;
}

// --- WM session approval gate --------------------------------------------

async function sliceBootstrap() {
  const raw = $("sliceCharacterGuid").value;
  const body = {
    marker_spell_id: Number($("markerSpellId").value || 946602),
    since_seconds: Number($("markerSinceSeconds").value || 300)
  };
  if (raw !== "") body.character_guid = Number(raw);
  try {
    const result = await api("/api/wm/session/bootstrap", { method: "POST", body: JSON.stringify(body) });
    state.sliceReady = result.ok === true;
    state.activeSession = result.session || null;
    if (result.character_guid != null) $("sliceCharacterGuid").value = result.character_guid;
    syncSessionInputs(state.activeSession);
    await refreshSlice();
  } catch (error) {
    renderSliceError(error.message);
  }
}

async function slicePoll() {
  try {
    const result = await api("/api/wm/session/poll", { method: "POST", body: "{}" });
    await refreshSlice();
    setOutput("sliceLog", `polled: ${result.events_seen} event(s); watermark=${result.last_seen_event_id ?? "?"}`);
  } catch (error) {
    renderSliceError(error.message);
  }
}

async function refreshSlice() {
  try {
    const kind = $("inboxKindFilter")?.value || "";
    const inboxPath = kind ? `/api/wm/inbox?kind=${encodeURIComponent(kind)}` : "/api/wm/inbox";
    const [status, pending, issues, log] = await Promise.all([
      api("/api/wm/session/status"),
      api(inboxPath),
      api("/api/wm/session/issues"),
      api("/api/wm/session/log")
    ]);
    renderSliceStatus(status);
    renderSlicePending(pending.pending || []);
    renderSliceIssues(issues.issues || []);
    setOutput("sliceLog", (log.log || []).slice(-20));
  } catch (error) {
    renderSliceError(error.message);
  }
  await refreshCharacterOverview();
}

function renderSliceStatus(status) {
  state.activeSession = status.session || state.activeSession;
  syncSessionInputs(state.activeSession);
  const rows = {
    "Character GUID": status.character_guid,
    "Source": state.activeSession?.source || "(unknown)",
    "Marker Spell": state.activeSession?.marker_spell_id || "(none)",
    "Current Beat": status.current_beat ?? "(none)",
    "Pending": status.pending_count,
    "Issues": status.issues_count,
    "Applied Log": status.applied_log_size
  };
  $("sliceStatus").innerHTML = Object.entries(rows)
    .map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(String(value))}</dd>`)
    .join("");
}

async function scanMarkers() {
  try {
    const query = new URLSearchParams({
      marker_spell_id: String(Number($("markerSpellId").value || 946602)),
      since_seconds: String(Number($("markerSinceSeconds").value || 300)),
      limit: "20"
    });
    const result = await api(`/api/wm/markers?${query.toString()}`);
    renderMarkerCandidates(result.candidates || []);
  } catch (error) {
    $("markerCandidates").innerHTML = `<p class="muted">${escapeHtml(error.message)}</p>`;
  }
}

function renderMarkerCandidates(items) {
  if (!items.length) {
    $("markerCandidates").innerHTML = `<p class="muted">No recent marker candidates.</p>`;
    return;
  }
  $("markerCandidates").innerHTML = items.map((item) => {
    const guid = item.character_guid || item.player_guid;
    const name = item.character_name || item.player_name || "(unknown)";
    return `
      <div class="card">
        <div class="card-head">
          <strong>${escapeHtml(String(guid))}</strong>
          <span class="badge">${escapeHtml(name)}</span>
          <span class="muted">event ${escapeHtml(String(item.bridge_event_id || "?"))}</span>
        </div>
        <div class="card-body">spell ${escapeHtml(String(item.spell_id || ""))}; online ${escapeHtml(String(item.character_online ?? "?"))}</div>
        <button data-marker-guid="${escapeHtml(String(guid))}">Use GUID</button>
      </div>
    `;
  }).join("");
  $("markerCandidates").querySelectorAll("[data-marker-guid]").forEach((button) => {
    button.addEventListener("click", () => {
      $("sliceCharacterGuid").value = button.dataset.markerGuid;
      $("watcherPlayerGuid").value = button.dataset.markerGuid;
    });
  });
}

function renderSlicePending(items) {
  if (!items.length) {
    $("slicePending").innerHTML = `<p class="muted">No pending proposals.</p>`;
    return;
  }
  $("slicePending").innerHTML = items.map((item) => `
    <div class="card" data-pending-id="${item.id}">
      <div class="card-head">
        <strong>#${item.id}</strong>
        <span class="badge">${escapeHtml(item.kind)}</span>
        <span class="muted">char ${escapeHtml(String(item.character_guid))}</span>
      </div>
      <div class="card-body">${escapeHtml(item.narrative_summary || "(no summary)")}</div>
      <pre class="output small">${escapeHtml(pretty(item.payload || {}))}</pre>
      <div class="button-row">
        <button class="primary" data-slice-approve="${item.id}">Approve</button>
        <button class="danger" data-slice-reject="${item.id}">Reject</button>
      </div>
    </div>
  `).join("");
  $("slicePending").querySelectorAll("[data-slice-approve]").forEach((button) => {
    button.addEventListener("click", () => sliceApprove(Number(button.dataset.sliceApprove)));
  });
  $("slicePending").querySelectorAll("[data-slice-reject]").forEach((button) => {
    button.addEventListener("click", () => sliceReject(Number(button.dataset.sliceReject)));
  });
}

function renderSliceIssues(items) {
  if (!items.length) {
    $("sliceIssues").innerHTML = `<p class="muted">No open issues.</p>`;
    return;
  }
  $("sliceIssues").innerHTML = items.map((item) => `
    <div class="card">
      <div class="card-head">
        <strong>#${item.id}</strong>
        <span class="badge">${escapeHtml(item.kind)}</span>
        <span class="muted">char ${escapeHtml(String(item.character_guid))}</span>
      </div>
      <div class="card-body">${escapeHtml(item.reason || "")}</div>
    </div>
  `).join("");
}

function renderSliceError(message) {
  $("sliceStatus").innerHTML = `<dt>Error</dt><dd>${escapeHtml(String(message))}</dd>`;
}

async function refreshCharacterOverview() {
  const empty = $("wm-character-empty");
  const body = $("wm-character-body");
  if (!empty || !body) return;
  let data;
  try {
    const response = await fetch("/api/wm/session/overview");
    data = await response.json();
  } catch (e) { return; }
  if (!data.ok || !data.overview) {
    empty.hidden = false;
    body.hidden = true;
    empty.textContent = data.error || "No active session. Bootstrap a character to see state.";
    return;
  }
  const o = data.overview;
  $("wm-char-guid").textContent = o.player_guid;
  $("wm-char-status").textContent = o.status;
  $("wm-char-arcs").textContent = o.counts.arc_states;
  $("wm-char-unlocks").textContent = o.counts.unlocks;
  $("wm-char-rewards").textContent = o.counts.rewards;
  $("wm-char-prompts").textContent = o.counts.prompt_queue;
  $("wm-char-proposals").textContent = o.proposals
    ? `${o.proposals.pending} pending / ${o.proposals.issues} issues` : "n/a";
  $("wm-char-readiness").textContent = o.readiness
    ? (o.readiness.ok ? "ready" : "not ready") : "n/a";
  empty.hidden = true;
  body.hidden = false;
}

async function sliceApprove(id) {
  try {
    await api("/api/wm/session/approve", { method: "POST", body: JSON.stringify({ id }) });
    await refreshSlice();
  } catch (error) {
    renderSliceError(error.message);
  }
}

async function sliceReject(id) {
  const reason = window.prompt("Reject reason:", "operator-rejected");
  if (reason === null) return;
  try {
    await api("/api/wm/session/reject", { method: "POST", body: JSON.stringify({ id, reason }) });
    await refreshSlice();
  } catch (error) {
    renderSliceError(error.message);
  }
}

async function sliceRollback() {
  const artifactType = $("rollbackArtifactType").value;
  const artifactEntry = Number($("rollbackArtifactEntry").value || 0);
  if (!artifactEntry) {
    $("rollbackResult").textContent = "Enter an artifact entry id.";
    return;
  }
  if (!window.confirm(`Roll back ${artifactType} ${artifactEntry}?`)) return;
  try {
    const result = await api("/api/wm/rollback", {
      method: "POST",
      body: JSON.stringify({ artifact_type: artifactType, artifact_entry: artifactEntry })
    });
    $("rollbackResult").textContent = pretty(result);
    await refreshSlice();
  } catch (error) {
    $("rollbackResult").textContent = error.message;
  }
}

async function simpleRollback() {
  $("rollbackArtifactType").value = $("simpleRollbackType").value;
  $("rollbackArtifactEntry").value = $("simpleRollbackEntry").value;
  await sliceRollback();
  setOutput("simpleActivity", $("rollbackResult").textContent || {});
}

function capitalize(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

init().catch((error) => {
  setOutput("jobOutput", { ok: false, error: error.message });
});
