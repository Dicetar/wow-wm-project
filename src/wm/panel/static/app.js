const state = {
  schemas: [],
  commands: [],
  activeSchema: null,
  formData: {},
  selectedDraft: null,
  latestJob: null
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
  bindTabs();
  bindEditorTabs();
  bindActions();
  await loadAll();
}

async function loadAll() {
  const [status, catalog, schemas, settings, drafts] = await Promise.all([
    api("/api/status"),
    api("/api/catalog"),
    api("/api/schemas"),
    api("/api/llm/settings"),
    api("/api/drafts")
  ]);
  state.commands = catalog.commands;
  state.schemas = schemas.schemas;
  renderStatus(status);
  renderSchemaSelects();
  renderCommands();
  renderSettings(settings);
  renderDrafts(drafts.drafts || []);
  selectSchema($("contentSchema").value || state.schemas[0]?.id);
}

function bindTabs() {
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".tab, .tab-panel").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      $(button.dataset.tab).classList.add("active");
    });
  });
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

function renderSchemaSelects() {
  const options = state.schemas.map((schema) => `<option value="${escapeHtml(schema.id)}">${escapeHtml(schema.label)}</option>`).join("");
  ["llmSchema", "contentSchema"].forEach((id) => {
    const current = $(id).value;
    $(id).innerHTML = options;
    if (current) $(id).value = current;
  });
}

function renderCommands() {
  renderCommandGroup("watcherCommands", ["watcher.status", "watcher.start", "watcher.stop", "bridge_lab.start"]);
  renderCommandGroup("nativeCommands", ["native.queue.inspect", "native.queue.recover", "native.queue.cleanup"], () => ({
    player_guid: Number($("watcherPlayerGuid").value || 5406),
    limit: Number($("watcherLimit").value || 20)
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
  $("llmMaxTokens").value = settings.max_tokens ?? 2048;
  $("llmTimeout").value = settings.timeout_seconds ?? 60;
  $("llmSchemaMode").value = settings.schema_mode || "json_schema";
  renderModelSelect(settings.model ? [settings.model] : [], settings.model);
}

function renderModelSelect(models, selected) {
  const unique = Array.from(new Set(models.filter(Boolean)));
  $("llmModel").innerHTML = [
    `<option value="">Select model</option>`,
    ...unique.map((model) => `<option value="${escapeHtml(model)}">${escapeHtml(model)}</option>`)
  ].join("");
  if (selected) $("llmModel").value = selected;
}

function currentLlmSettings() {
  return {
    base_url: $("llmBaseUrl").value,
    model: $("llmModel").value || null,
    temperature: Number($("llmTemperature").value || 0.2),
    max_tokens: Number($("llmMaxTokens").value || 2048),
    timeout_seconds: Number($("llmTimeout").value || 60),
    schema_mode: $("llmSchemaMode").value,
    api_key: $("llmApiKey").value || null
  };
}

async function saveLlmSettings() {
  const result = await api("/api/llm/settings", { method: "POST", body: JSON.stringify(currentLlmSettings()) });
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
  $("draftList").innerHTML = drafts.map((draft) => {
    const label = `${draft.created_at || ""} | ${draft.origin} | ${draft.schema_version} | ${draft.state}`;
    return `<button data-draft-id="${escapeHtml(draft.draft_id)}">${escapeHtml(label)}</button>`;
  }).join("");
  $("draftList").querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", async () => {
      state.selectedDraft = await api(`/api/drafts/${encodeURIComponent(button.dataset.draftId)}`);
      setOutput("draftDetail", state.selectedDraft);
    });
  });
}

async function adoptSelectedDraft() {
  if (!state.selectedDraft) return;
  const adopted = await api(`/api/drafts/${encodeURIComponent(state.selectedDraft.draft_id)}/adopt`, {
    method: "POST",
    body: JSON.stringify({ operator_name: "operator-reviewed" })
  });
  state.selectedDraft = adopted;
  setOutput("draftDetail", adopted);
  await refreshDrafts();
}

async function rejectSelectedDraft() {
  if (!state.selectedDraft) return;
  const rejected = await api(`/api/drafts/${encodeURIComponent(state.selectedDraft.draft_id)}/reject`, {
    method: "POST",
    body: JSON.stringify({})
  });
  state.selectedDraft = rejected;
  setOutput("draftDetail", rejected);
  await refreshDrafts();
}

async function dryRunSelectedDraft() {
  if (!state.selectedDraft || !state.selectedDraft.parsed_json) return;
  if (state.selectedDraft.origin !== "human_reviewed") {
    setOutput("draftDetail", {
      ok: false,
      error: "Adopt the draft as reviewed before dry-run. LLM drafts never run directly.",
      draft: state.selectedDraft
    });
    return;
  }
  const schemaVersion = state.selectedDraft.schema_version;
  const commandId = schemaVersion === "control.proposal.v1" ? "control.apply" : "content.release.plan";
  await runCommand(commandId, {}, state.selectedDraft.parsed_json, "draftDetail");
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
