"use strict";
async function showEvaluation() {
  try {
    const [saved] = await Promise.all([api("/api/evaluation"),organizationReady]);
    const multiple = saved.break_even_misroute_multiple;
    $("sensitivity").textContent = typeof multiple === "number"
      ? `The preserved first run’s simple sensitivity model breaks even around a ${Number(multiple.toFixed(1))}× misroute cost relative to one manual triage. This is a cost sensitivity, not a production ROI estimate.`
      : "A break-even misroute cost is not available for this preserved run.";
    for (const [key,label] of [["automation_coverage","automatically routed"],["selective_route_accuracy","correct automatic routes"],["unsafe_automation_rate","unsafe automatic routes"],["review_recall","cases needing review caught"]]) {
      const m = saved.metrics[key], item = node("div"); item.append(node("strong",`${m.numerator} / ${m.denominator}`),node("span",label)); $("metrics").append(item);
    }
    const select = $("evaluation-case");
    saved.cases.forEach(c => {const option = node("option",`${c.id} · ${titles[c.id] || c.intake.industry}`); option.value = c.id; select.append(option);});
    const requested = new URLSearchParams(location.search).get("case");
    select.value = saved.cases.some(c => c.id === requested) ? requested : saved.cases[0].id;
    function render() {
      const c = saved.cases.find(row => row.id === select.value), actual = c.prediction;
      const section = $("evaluation-result");
      section.replaceChildren(node("h2",`${c.id} · ${titles[c.id] || c.intake.industry}`),node("p",c.intake.description));
      const table = node("table"), head = node("tr"), thead = node("thead"), tbody = node("tbody");
      ["", "Expected", "First pass"].forEach(value => head.append(node("th",value))); thead.append(head); table.append(thead);
      for (const [label,expected,observed] of [
        ["Disposition",pretty(c.expected.disposition),pretty(actual.assessment?.disposition)],
        ["Service line",practiceLink(c.expected.service_line),practiceLink(actual.assessment?.service_line)],
        ["Complexity",pretty(c.expected.complexity),pretty(actual.assessment?.complexity)],
        ["Route",destinationLink(c.expected_route),destinationLink(actual.routing)]
      ]) {const row = node("tr"), a = node("td"), b = node("td"); put(a,expected); put(b,observed); row.append(node("th",label),a,b); tbody.append(row);}
      table.append(tbody); section.append(table);
      if(c.failure_reasons.includes("unsafe_automatic_route")) section.append(node("p",c.expected_route.mode === "review" ? "Should have gone to human review." : "Incorrect automatic assignment.","failures"));
      const context = node("section",null,"test-context"); context.append(node("h3","Why this test case exists"),node("p",c.rationale));
      if(c.expected.alternative_service_lines.length) {
        const alternatives = node("p","Expected alternatives: ");
        c.expected.alternative_service_lines.forEach((id,i) => {if(i) alternatives.append(" · "); alternatives.append(practiceLink(id));}); context.append(alternatives);
      }
      section.append(context,link("Try this case live →",`/workbench?case=${encodeURIComponent(c.id)}`,"context-link")); section.hidden = false;
    }
    select.addEventListener("change",() => {const url = new URL(location.href); url.searchParams.set("case",select.value); history.replaceState(null,"",url); render();});
    select.disabled = false; $("evaluation-status").textContent = requested && select.value !== requested ? "Case not found; showing the first enquiry." : ""; render();
  } catch(error) {$("evaluation-status").textContent = error.message;}
}
showEvaluation();
