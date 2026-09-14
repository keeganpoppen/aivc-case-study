"use strict";
const HELP = {
  Disposition: "Whether the enquiry is clear enough to route, has multiple plausible owners, lacks necessary information, or falls outside the offered services.",
  Complexity: "The scope and coordination the work requires: simple, moderate, or complex. Company size is evidence, not a complexity label; urgency does not increase complexity.",
  Assignment: "Automatic assignment occurs when the structured assessment is sufficiently clear under configured policy. Ambiguous, insufficient-information, out-of-scope, and operational-failure cases go to human review.",
  "Benchmark check": "Expected is the frozen authored answer. Live is the result of the model call just run. The preserved first-pass evaluation is separate and may differ because model outputs are stochastic. The four headline rows are checked; the rationale and expected alternatives explain the case."
};
let helpId = 0;
function infoHelp(topic) {
  const wrap = node("span",null,"context-help"), button = node("button","ⓘ","help-button");
  const popup = node("span",HELP[topic],"help-popover"); popup.id = `help-${++helpId}`;
  popup.setAttribute("popover","auto"); popup.setAttribute("role","tooltip");
  button.type = "button"; button.setAttribute("aria-label",`About ${topic.toLowerCase()}`);
  button.setAttribute("aria-describedby",popup.id); button.setAttribute("aria-controls",popup.id);
  button.setAttribute("aria-expanded","false");
  let pinned = false, timer;
  function open() {
    clearTimeout(timer);
    if (!popup.matches(":popover-open")) popup.showPopover();
    const anchor = button.getBoundingClientRect(), rect = popup.getBoundingClientRect();
    popup.style.left = `${Math.max(8,Math.min(anchor.left,innerWidth-rect.width-8))}px`;
    popup.style.top = `${anchor.bottom+rect.height+8 < innerHeight ? anchor.bottom+6 : Math.max(8,anchor.top-rect.height-6)}px`;
  }
  function close() {clearTimeout(timer); if (popup.matches(":popover-open")) popup.hidePopover(); pinned = false;}
  function leave() {timer = setTimeout(() => {if (!pinned && document.activeElement !== button && !wrap.matches(":hover") && !popup.matches(":hover")) close();},150);}
  button.addEventListener("pointerenter",open); button.addEventListener("focus",open);
  button.addEventListener("click",() => {if(pinned) close(); else {open(); pinned = true;}});
  button.addEventListener("blur",() => {pinned = false; leave();});
  wrap.addEventListener("pointerleave",leave); popup.addEventListener("pointerenter",() => clearTimeout(timer)); popup.addEventListener("pointerleave",leave);
  button.addEventListener("keydown",event => {if(event.key === "Escape") {close(); event.preventDefault();}});
  popup.addEventListener("toggle",() => {const visible = popup.matches(":popover-open"); button.setAttribute("aria-expanded",String(visible)); if(!visible) pinned = false;});
  wrap.append(button,popup); return wrap;
}
