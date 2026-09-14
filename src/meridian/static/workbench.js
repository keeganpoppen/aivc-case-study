"use strict";
const form = $("intake");
const keys = ["industry", "company_size", "urgency", "description"];
const dispositions = {clear:"clear", ambiguous:"ambiguous", insufficient_information:"needs review", out_of_scope:"out of scope"};
const failureText = {
  unsafe_automatic_route:"Incorrect automatic assignment.", unnecessary_review:"Could have been assigned automatically.",
  service_line_mismatch:"Different practice selected.", complexity_mismatch:"Different complexity assessment.",
  disposition_mismatch:"Different assessment of readiness to route."
};
const operationalText = {
  client_configuration_error:"API credentials unavailable", timeout:"Request timed out", connection_error:"Connection failed",
  api_status_error:"API request failed", refusal:"Model declined the request", incomplete_response:"Incomplete response",
  missing_structured_output:"No structured assessment returned", invalid_structured_semantics:"Assessment failed validation", sdk_error:"API client error"
};
let config, selected = null, modified = false, generated = false, result = null, busy = false, revision = 0;
const readForm = () => Object.fromEntries(keys.map(k => [k, form.elements[k].value]));
function status(text = "", error = false) { $("status").textContent = text; $("status").className = error ? "error" : ""; }
function clearResult() {
  revision++; result = null; $("results").hidden = true; $("comparison").hidden = true;
  $("comparison-body").replaceChildren(); status();
}
function source() {
  $("source").textContent = selected ? `${selected.id} · ${modified ? "modified" : "test"}` : generated ? "Generated example" : "New enquiry";
  document.querySelectorAll(".case").forEach(b => b.setAttribute("aria-current", String(b.dataset.id === selected?.id)));
}
function populate(values, item = null, isGenerated = false) {
  keys.forEach(k => {form.elements[k].value = values[k] || "";});
  selected = item; modified = false; generated = isGenerated; clearResult(); source();
}
function setBusy(value) {
  busy = value; $("fields").disabled = value;
  document.querySelectorAll("button:not(.help-button)").forEach(b => {b.disabled = value;}); $("scenario").disabled = value;
  $("intake").setAttribute("aria-busy", String(value));
}
function definitions(id, entries) {
  $(id).replaceChildren(...entries.map(([key,value]) => {
    const row = node("div"), dd = node("dd"); put(dd,value); const label = node("dt",key);
    if (id === "assessment" && HELP[key]) label.append(infoHelp(key));
    row.append(label,dd); return row;
  }));
}
function alternativeLinks(lines) {
  const span = node("span");
  lines.forEach((id,i) => {if(i) span.append(" · "); span.append(practiceLink(id));});
  return lines.length ? span : "—";
}
function showResult(value) {
  result = value;
  const a = value.assessment, r = value.routing, m = value.metadata;
  $("summary").textContent = a?.summary || "Assessment unavailable. Human review required.";
  definitions("assessment", [
    ["Disposition",dispositions[a?.disposition] || "—"], ["Service line",practiceLink(a?.service_line)],
    ["Complexity",pretty(a?.complexity)],
    ...(a?.alternative_service_lines.length ? [["Alternatives",alternativeLinks(a.alternative_service_lines)]] : []),
    ...(a?.review_reasons.length ? [[a.review_reasons.length === 1 ? "Review reason" : "Review reasons",a.review_reasons.join(" ")]] : [])
  ]);
  $("mode").textContent = r.mode === "automatic" ? "AUTOMATIC ASSIGNMENT" : "HUMAN REVIEW";
  $("mode").append(infoHelp("Assignment"));
  put($("destination"),destinationLink(r));
  document.querySelector(".route-card").classList.toggle("review",r.mode === "review");
  definitions("routing",[["Practice",practiceLink(r.service_line)],["Priority",pretty(r.priority)],["Response target",pretty(r.target_response)]]);
  definitions("metadata",[
    ["Model",m.model],["Elapsed",`${m.elapsed_seconds.toFixed(2)} s`],["Tokens in / out",`${pretty(m.input_tokens)} / ${pretty(m.output_tokens)}`],
    ["Reasoning tokens",pretty(m.reasoning_tokens)],["Call",m.state === "completed" ? "Completed" : "Fallback"],
    ["Routing rule",pretty(r.rule)], ...(m.failure_reason ? [["Failure",operationalText[m.failure_reason] || pretty(m.failure_reason)]] : [])
  ]);
  $("results").hidden = false;
}
async function compare(intake, actual, caseId) {
  const current = revision;
  $("comparison").hidden = false; $("comparison-count").textContent = "CHECKING…";
  $("comparison-body").textContent = "Checking against the test case…";
  try {
    const score = await api(`/api/cases/${encodeURIComponent(caseId)}/expected`,{intake,result:actual});
    if (current !== revision) return;
    const expected = score.expected, a = actual.assessment, er = score.expected_route, ar = actual.routing;
    // Display equality is a four-field check; scoring explanations come from the server.
    const rows = [
      ["Disposition", dispositions[expected.disposition], dispositions[a?.disposition] || "—", expected.disposition === a?.disposition],
      ["Service line",practiceLink(expected.service_line),practiceLink(a?.service_line),expected.service_line === (a?.service_line ?? null)],
      ["Complexity",pretty(expected.complexity),pretty(a?.complexity),expected.complexity === (a?.complexity ?? null)],
      ["Route",destinationLink(er),destinationLink(ar),er.mode === ar.mode && er.destination === ar.destination]
    ];
    const differences = rows.filter(row => !row[3]).length;
    $("comparison-count").textContent = differences ? `${differences} DIFFERENCE${differences === 1 ? "" : "S"}` : "4 / 4 MATCH";
    $("comparison-count").classList.toggle("warning", differences > 0);
    const table = node("table"), thead = node("thead"), head = node("tr");
    ["", "Expected", "Live", ""].forEach(text => head.append(node("th",text))); thead.append(head); table.append(thead);
    const tbody = node("tbody");
    rows.forEach(([label, expectedValue, liveValue, matches]) => {
      const row = node("tr"), expectedCell = node("td",null,matches ? "" : "mismatch"), liveCell = node("td",null,matches ? "" : "mismatch");
      put(expectedCell,expectedValue); put(liveCell,liveValue);
      const mark = node("td",matches ? "✓" : "✕",matches ? "match-mark" : "error"); mark.setAttribute("aria-label",matches ? "Match" : "Difference");
      row.append(node("th",label),expectedCell,liveCell,mark); tbody.append(row);
    });
    table.append(tbody); $("comparison-body").replaceChildren(table);
    const unsafeReview = score.failure_reasons.includes("unsafe_automatic_route") && score.expected_review;
    const messages = score.failure_reasons.flatMap(reason => {
      if (reason === "unsafe_automatic_route" && unsafeReview) return ["Should have gone to human review."];
      if (reason === "disposition_mismatch" && unsafeReview) return [];
      if (reason.startsWith("operational:")) return [operationalText[reason.slice(12)] || "The model call failed."];
      return [failureText[reason] || "Result differs from the test expectation."];
    });
    if(messages.length) $("comparison-body").append(node("p",messages.join(" "),"failures"));
    const context = node("section",null,"test-context");
    context.append(node("h3","Why this test case exists"));
    if (expected.alternative_service_lines.length) {
      const alternatives = node("p");
      alternatives.append(node("span","Expected alternatives: ","muted"),alternativeLinks(expected.alternative_service_lines));
      context.append(alternatives);
    }
    context.append(node("p",score.rationale),link("View in first-pass evaluation →", `/evaluation?case=${encodeURIComponent(caseId)}`, "context-link"));
    $("comparison-body").append(context);
  } catch(error) {
    if (current === revision) {$("comparison-count").textContent = "UNAVAILABLE"; $("comparison-body").textContent = error.message;}
  }
}
form.addEventListener("input", () => {if (busy) return; if (selected) modified = true; clearResult(); source();});
$("manual").onclick = () => populate({company_size:Object.keys(config.company_size)[0],urgency:Object.keys(config.urgency)[0]});
$("generator-toggle").onclick = () => {
  const open = $("generator-panel").hidden; $("generator-panel").hidden = !open;
  $("generator-toggle").setAttribute("aria-expanded",String(open)); if(open) $("scenario").focus();
};
form.addEventListener("submit", async event => {
  event.preventDefault(); if (busy) return;
  const intake = readForm(), caseId = selected && !modified ? selected.id : null;
  clearResult(); setBusy(true); status("Assessing enquiry…");
  try {
    const actual = await api("/api/triage",intake); showResult(actual); status();
    if (caseId) await compare(intake,actual,caseId);
  } catch(error) {status(error.message,true);} finally {setBusy(false);}
});
$("generator").addEventListener("submit", async event => {
  event.preventDefault(); if (busy) return; setBusy(true); status("Generating example…");
  try {
    populate(await api("/api/generate",{prompt:$("scenario").value}),null,true);
    $("generator-panel").hidden = true; $("generator-toggle").setAttribute("aria-expanded","false");
  } catch(error) {status(error.message,true);} finally {setBusy(false);}
});
async function initialize() {
  setBusy(true);
  try {
    const [settings,cases] = await Promise.all([api("/api/config"),api("/api/cases"),organizationReady]); config = settings;
    for (const key of ["company_size","urgency"]) Object.entries(config[key]).forEach(([value,choice]) => {
      const option = node("option",choice.display.replace(/(\d)-(\d)/g,"$1–$2")); option.value = value; form.elements[key].append(option);
    });
    for (const [label,prefixes] of [["Routine",["S"]],["Boundary cases",["H"]],["Needs review",["A","I","O"]]]) {
      const members = cases.filter(c => prefixes.includes(c.id[0]));
      const group = node("details",null,"case-group"); group.open = label !== "Routine";
      group.append(node("summary",`${label} (${members.length})`));
      $("cases").append(group);
      members.forEach(c => {
        const b = node("button",`${c.id} · ${titles[c.id] || c.form.industry}`,"case"); b.dataset.id = c.id;
        b.append(node("small",c.form.industry)); b.onclick = () => {if (!busy) {group.open = true; populate(c.form,c);}}; group.append(b);
      });
    }
    if(config.snapshot) {
      const m = config.snapshot, auto = m.automation_coverage, correct = m.selective_route_accuracy;
      $("evaluation-story").textContent = `On the first run, before seeing any results, we tested ${auto.denominator} synthetic enquiries chosen to include difficult boundary and review cases. The system automatically routed ${auto.numerator}; ${correct.numerator} of those routes were correct.`;
      for (const [key,label,countOnly] of [["selective_route_accuracy","correct automatic routes"],["unsafe_automation_rate","unsafe automatic routes",true],["review_recall","cases needing review caught"],["service_line_accuracy","service lines correct"],["complexity_accuracy","complexity labels correct"]]) {
        const metric = m[key], item = node("div"); item.append(node("strong",countOnly ? `${metric.numerator}` : `${metric.numerator} / ${metric.denominator}`),node("span",label)); $("metrics").append(item);
      }
      $("snapshot").hidden = false;
    }
    $("comparison").querySelector("h2").append(infoHelp("Benchmark check"));
    const requested = new URLSearchParams(location.search).get("case");
    const testCase = cases.find(c => c.id === requested);
    if (testCase) {
      populate(testCase.form,testCase);
      document.querySelector(`.case[data-id="${testCase.id}"]`).closest("details").open = true;
    } else if (requested) status("Test case not found. Choose an enquiry from the sidebar.",true);
    source(); setBusy(false);
  } catch(error) {status(`Could not load intake: ${error.message}. Refresh to retry.`,true);}
}
initialize();
