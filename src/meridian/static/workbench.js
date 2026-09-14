"use strict";
const $ = (id) => document.getElementById(id);
const form = $("intake");
const keys = ["industry", "company_size", "urgency", "description"];
let config, selected = null, modified = false, generated = false, result = null, busy = false, revision = 0;
const readForm = () => Object.fromEntries(keys.map(k => [k, form.elements[k].value]));
const pretty = value => value == null ? "—" : String(value).replaceAll("_", " ");
const line = value => config.service_lines[value] || pretty(value);
function node(tag, text, className) { const n = document.createElement(tag); if (text != null) n.textContent = text; if (className) n.className = className; return n; }
async function api(url, body) {
  const response = await fetch(url, body === undefined ? {} : {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Check the submitted fields and try again.");
  return data;
}
function status(text = "", error = false) { $("status").textContent = text; $("status").className = error ? "error" : ""; }
function clearResult() { revision++; result = null; $("results").hidden = true; $("comparison").hidden = true; $("comparison").open = false; $("comparison-body").replaceChildren(); status(); }
function source() {
  $("source").textContent = selected ? `${selected.id} / ${modified ? "Modified · ad-hoc" : "Frozen benchmark"}` : generated ? "Generated / ephemeral" : "Manual enquiry";
  document.querySelectorAll(".case").forEach(b => b.setAttribute("aria-current", String(b.dataset.id === selected?.id)));
}
function populate(values, item = null, isGenerated = false) {
  keys.forEach(k => {form.elements[k].value = values[k] || "";}); selected = item; modified = false; generated = isGenerated;
  clearResult(); source();
}
function setBusy(value) {
  busy = value; $("fields").disabled = value;
  document.querySelectorAll("button").forEach(b => {b.disabled = value;}); $("scenario").disabled = value;
  $("intake").setAttribute("aria-busy", String(value));
}
function definitions(id, entries) {
  $(id).replaceChildren(...entries.map(([key,value]) => {const row = node("div"); row.append(node("dt",key),node("dd",value)); return row;}));
}
function showResult(value) {
  result = value; const a = value.assessment, r = value.routing, m = value.metadata;
  $("summary").textContent = a?.summary || "No validated semantic assessment is available. Routing policy selects human review.";
  definitions("assessment", [["Disposition",pretty(a?.disposition)],["Service line",line(a?.service_line)],["Complexity",pretty(a?.complexity)],["Alternatives",a?.alternative_service_lines.map(line).join("; ") || "—"],["Review reasons",a?.review_reasons.join(" ") || "—"]]);
  $("mode").textContent = r.mode === "automatic" ? "AUTOMATIC ROUTE" : "HUMAN REVIEW";
  $("destination").textContent = r.destination;
  document.querySelector(".route-card").classList.toggle("review",r.mode === "review");
  definitions("routing",[["Service line",line(r.service_line)],["Routing rule",pretty(r.rule)],["Priority",pretty(r.priority)],["Response target",pretty(r.target_response)]]);
  definitions("metadata",[["Model",m.model],["Elapsed",`${m.elapsed_seconds.toFixed(2)} s`],["Input tokens",pretty(m.input_tokens)],["Output tokens",pretty(m.output_tokens)],["Reasoning tokens",pretty(m.reasoning_tokens)],["State",pretty(m.state)],["Fallback reason",pretty(m.failure_reason)]]);
  $("results").hidden = false; $("comparison").hidden = !(selected && !modified);
}
form.addEventListener("input", () => { if (busy) return; if (selected) modified = true; clearResult(); source(); });
$("manual").onclick = () => populate({company_size:Object.keys(config.company_size)[0],urgency:Object.keys(config.urgency)[0]});
form.addEventListener("submit", async event => {
  event.preventDefault(); if (busy) return; const intake = readForm(); clearResult(); setBusy(true); status("Assessing enquiry…");
  try {showResult(await api("/api/triage",intake)); status("Triage complete.");} catch(error) {status(error.message,true);} finally {setBusy(false);}
});
$("generator").addEventListener("submit", async event => {
  event.preventDefault(); if (busy) return; setBusy(true); status("Generating fictional form data…");
  try {const value = await api("/api/generate",{prompt:$("scenario").value}); populate(value,null,true); status("Fictional enquiry ready. Edit it or run triage.");} catch(error) {status(error.message,true);} finally {setBusy(false);}
});
$("comparison").addEventListener("toggle", async () => {
  if (!$("comparison").open || !selected || modified || !result) return;
  const current = revision, actual = result; $("comparison-body").textContent = "Loading expectation…";
  try {
    const score = await api(`/api/cases/${encodeURIComponent(selected.id)}/expected`,{intake:readForm(),result:actual});
    if (current !== revision) return;
    const table = node("table"), head = node("tr"); head.append(node("th",""),node("th","Expected"),node("th","Actual · live run")); const thead = node("thead"); thead.append(head); table.append(thead); const tbody = node("tbody");
    const routeName = r => r.mode === "review" ? `HUMAN REVIEW · ${r.destination}` : r.destination;
    [["Disposition",pretty(score.expected.disposition),pretty(actual.assessment?.disposition)], ["Service line",line(score.expected.service_line),line(actual.assessment?.service_line)], ["Complexity",pretty(score.expected.complexity),pretty(actual.assessment?.complexity)], ["Route",routeName(score.expected_route),routeName(actual.routing)]].forEach(([label,expected,predicted]) => {const row = node("tr",null,expected !== predicted ? "mismatch" : ""); row.append(node("th",label),node("td",expected),node("td",predicted)); tbody.append(row);});
    table.append(tbody); $("comparison-body").replaceChildren(table);
    $("comparison-body").append(node("p",score.failure_reasons.length ? score.failure_reasons.map(pretty).join(" · ") : "No mechanically scored failures for this run.",score.failure_reasons.length ? "failures" : "muted"));
    $("comparison-body").append(node("p","Expected route is derived from frozen semantics and current routing policy. Prose and alternatives are not auto-scored.","muted"));
  } catch(error) {if (current === revision) $("comparison-body").textContent = error.message;}
});
async function initialize() {
  setBusy(true);
  try {
    const [settings,cases] = await Promise.all([api("/api/config"),api("/api/cases")]); config = settings;
    for (const key of ["company_size","urgency"]) Object.entries(config[key]).forEach(([value,choice]) => {const option = node("option",choice.display.replace(/(\d)-(\d)/g,"$1–$2")); option.value = value; form.elements[key].append(option);});
    $("practices").replaceChildren(...Object.values(config.service_lines).map(name => node("span",name)));
    for (const [label,prefixes] of [["Straightforward",["S"]],["Boundary cases",["H"]],["Human-review cases",["A","I","O"]]]) {
      $("cases").append(node("h3",label)); cases.filter(c => prefixes.includes(c.id[0])).forEach(c => {
        const b = node("button",`${c.id} · ${c.form.industry}`,"case"); b.dataset.id = c.id; b.title = c.form.description;
        b.append(node("small",c.form.description)); b.onclick = () => {if (!busy) populate(c.form,c);}; $("cases").append(b);
      });
    }
    if(config.snapshot) {
      for (const key of ["automation_coverage","selective_route_accuracy","unsafe_automation_rate","review_recall","service_line_accuracy"]) {const item = node("div"), value = config.snapshot[key].value; item.append(node("strong",typeof value === "number" ? `${+(value*100).toFixed(1)}%` : value),node("span",pretty(key))); $("metrics").append(item);}
      $("snapshot").hidden = false;
    }
    source();
    setBusy(false);
  } catch(error) {status(`Workbench could not load: ${error.message}. Refresh to retry.`,true);}
}
initialize();
