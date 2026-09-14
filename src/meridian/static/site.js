"use strict";
const $ = id => document.getElementById(id);
function node(tag, text, className) {
  const el = document.createElement(tag);
  if (text != null) el.textContent = text;
  if (className) el.className = className;
  return el;
}
function link(text, href, className) {
  const el = node("a", text, className); el.href = href; return el;
}
function put(el, value) { el.replaceChildren(); el.append(value instanceof Node ? value : document.createTextNode(value ?? "—")); }
const pretty = value => value == null ? "—" : String(value).replaceAll("_", " ");
async function api(url, body) {
  const response = await fetch(url, body === undefined ? {} : {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)
  });
  if (!response.headers.get("content-type")?.includes("application/json")) throw new Error("Server unavailable. Please try again.");
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Check the submitted fields and try again.");
  return data;
}
let organization;
const organizationReady = api("/api/site").then(data => {organization = data; return data;});
function practiceLink(id) { return id && organization.practices[id] ? link(organization.practices[id].name, `/practices/${id}`) : node("span", pretty(id)); }
function personLink(slug) { const person = organization.people[slug]; return link(person.name, `/people/${slug}`); }
function destinationLink(route) {
  const person = Object.values(organization.people).find(p => p.name === route.destination);
  return route.mode === "automatic" && person ? personLink(person.slug) : node("span", route.destination);
}
function personCard(person) {
  const card = node("article", null, "person-card");
  card.append(node("div", person.roles.map(r => r.role).join(" / "), "eyebrow"), personLink(person.slug));
  person.roles.forEach(r => card.append(practiceLink(r.practice)));
  return card;
}
function list(items) { const ul = node("ul"); items.forEach(item => ul.append(node("li", item))); return ul; }
async function showSite() {
  try {
    await organizationReady;
    const main = $("site-content");
    if (!main) return;
    const [, section, id] = location.pathname.split("/");
    if (!section) {
      const hero = node("section", null, "hero");
      hero.append(node("div", "MERIDIAN ADVISORY", "eyebrow"), node("h1", "Business problems rarely respect the org chart."),
        node("p", organization.firm.positioning), link("Tell us what needs to change →", "/workbench", "button"));
      const practices = node("section", null, "site-section"); practices.id = "practices";
      practices.append(node("div", "SIX PRACTICES", "eyebrow"), node("h2", "Different disciplines. Shared problems."));
      const grid = node("div", null, "practice-grid");
      Object.values(organization.practices).forEach((p, i) => {
        const card = node("article", null, "practice-card");
        card.append(node("span", `0${i+1}`, "eyebrow"), practiceLink(p.id), list(p.owns.slice(0,3))); grid.append(card);
      });
      practices.append(grid);
      const people = node("section", null, "site-section"); people.id = "people";
      people.append(node("h2", "Our people"));
      const team = node("div", null, "people-grid"); Object.values(organization.people).forEach(p => team.append(personCard(p))); people.append(team);
      main.replaceChildren(hero, practices, people);
    } else if (section === "practices") {
      const p = organization.practices[id]; document.title = `${p.name} · Meridian Advisory`;
      const hero = node("section", null, "page-hero");
      hero.append(link("← All practices", "/#practices", "muted"), node("h1", p.name), node("p", p.boundary));
      const content = node("section", null, "practice-detail");
      const scope = node("div"); scope.append(node("h2", "How we help"), list(p.owns));
      const leads = node("div"); leads.append(node("h2", "Practice leadership"), personCard(organization.people[p.default_lead]), personCard(organization.people[p.senior_lead]));
      content.append(scope, leads);
      const examples = node("section", null, "site-section"); examples.append(node("h2", "Engagement scope"));
      const grid = node("div", null, "practice-grid");
      Object.entries(p.complexity_signals).forEach(([level, signals]) => {const card = node("article", null, "practice-card"); card.append(node("h3", pretty(level)), list(signals)); grid.append(card);});
      examples.append(grid); main.replaceChildren(hero, content, examples, link("Discuss an enquiry →", "/workbench", "button"));
    } else {
      const p = organization.people[id]; document.title = `${p.name} · Meridian Advisory`;
      const hero = node("section", null, "page-hero"); hero.append(link("← Our people", "/#people", "muted"), node("h1", p.name)); main.replaceChildren(hero);
      p.roles.forEach(role => {
        const block = node("section", null, "person-detail"); block.append(node("div", role.role, "eyebrow"), practiceLink(role.practice), node("h2", "Enquiries handled by this role"));
        block.append(node("p", "For enquiries ready for automatic assignment, the current intake policy allocates the following scope to this lead."));
        const dl = node("dl"); role.routing_examples.forEach(example => {const row = node("div"); row.append(node("dt", example.company_size), node("dd", example.complexities.join(" · "))); dl.append(row);});
        if (!role.routing_examples.length) block.append(node("p", "No automatic assignments under the current intake policy."));
        block.append(dl); main.append(block);
      });
      main.append(link("Submit an enquiry →", "/workbench", "button"));
    }
  } catch(error) {if ($("site-content")) $("site-content").textContent = error.message;}
}
showSite();
