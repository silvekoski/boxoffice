/* Shared helpers for the scenes. No timers, no randomness, no network: all output is a function of timeline time. */
(function () {
  const SVGNS = "http://www.w3.org/2000/svg";
  const TIMING = window.VID_TIMING || { lead: 0.2, scenes: {}, cues: {} };
  const norm = (w) => w.toLowerCase().replace(/[^a-z0-9]/g, "");

  const VID = {
    data: window.VIDEO_DATA || {},
    timing: TIMING,
    color: { bg: "#0E1116", paper: "#F4F1EA", blue: "#4C9BE8", amber: "#F0A63A", green: "#3FBF8F", red: "#E5604D", grey: "#8A93A3", ink: "#E8ECF2" },

    /* Scene length in seconds. */
    dur(scene) { return TIMING.scenes[scene].dur; },

    /* Time (scene clock) when the voice starts to say `phrase`. nth picks a later occurrence. edge "e" gives the end of the phrase. */
    t(scene, phrase, nth, edge) {
      const words = TIMING.scenes[scene].words;
      const want = phrase.split(/\s+/).map(norm).filter(Boolean);
      let seen = 0;
      for (let i = 0; i + want.length <= words.length; i++) {
        let ok = true;
        for (let k = 0; k < want.length; k++) if (norm(words[i + k][0]) !== want[k]) { ok = false; break; }
        if (ok) {
          if (seen === (nth || 0)) return TIMING.lead + (edge === "e" ? words[i + want.length - 1][2] : words[i][1]);
          seen++;
        }
      }
      throw new Error("phrase not in narration of " + scene + ": " + phrase);
    },

    svg(tag, attrs, parent) {
      const el = document.createElementNS(SVGNS, tag);
      for (const k in attrs || {}) el.setAttribute(k, attrs[k]);
      if (parent) parent.appendChild(el);
      return el;
    },
    el(tag, cls, parent, text) {
      const el = document.createElement(tag);
      if (cls) el.className = cls;
      if (text != null) el.textContent = text;
      if (parent) parent.appendChild(el);
      return el;
    },
    path(pts, closed) {
      return "M" + pts.map((p) => p[0] + " " + p[1]).join("L") + (closed ? "Z" : "");
    },

    /* Text that types on: one span per character, shown in order. */
    typeOn(tl, el, text, start, duration) {
      el.textContent = "";
      const spans = [];
      for (const ch of text) {
        if (ch === "\n") { el.appendChild(document.createElement("br")); continue; }
        const s = document.createElement("span");
        s.textContent = ch;
        s.style.opacity = "0";
        el.appendChild(s);
        spans.push(s);
      }
      tl.fromTo(spans, { opacity: 0 }, { opacity: 1, duration: 0.02, ease: "none", stagger: duration / spans.length }, start);
    },

    /* A number that ticks linearly from a to b. fmt turns the value into text. */
    counter(tl, el, a, b, start, duration, fmt) {
      const o = { v: a };
      const show = () => { el.textContent = fmt(o.v); };
      el.textContent = fmt(a);
      tl.fromTo(o, { v: a }, { v: b, duration, ease: "none", onUpdate: show }, start);
    },

    /* Entrance: fade and rise. */
    enter(tl, target, start, opts) {
      const o = Object.assign({ y: 18, duration: 0.5 }, opts || {});
      tl.fromTo(target, { opacity: 0, y: o.y }, { opacity: 1, y: 0, duration: o.duration, ease: "power2.out", stagger: o.stagger || 0 }, start);
    },
    fadeOut(tl, target, start, duration) {
      tl.to(target, { opacity: 0, duration: duration || 0.3, ease: "power1.in" }, start);
    },

    /* Draw a stroke from its start to its end. */
    draw(tl, pathEl, start, duration, ease) {
      const len = pathEl.getTotalLength ? pathEl.getTotalLength() : 1000;
      pathEl.style.strokeDasharray = len;
      // hidden until the stroke starts: a zero-length dash with a round cap would show as a dot
      gsap.set(pathEl, { strokeDashoffset: len, opacity: 0 });
      tl.to(pathEl, { opacity: 1, duration: 0.05, ease: "none" }, start);
      tl.to(pathEl, { strokeDashoffset: 0, duration, ease: ease || "power2.inOut" }, start);
    },

    /* The numbered amber mark of a counted item, built in an SVG in drawing pixels. */
    mark(svg, x, y, n, r) {
      const g = VID.svg("g", { class: "mark", transform: "translate(" + x + " " + y + ")" }, svg);
      const inner = VID.svg("g", {}, g);
      VID.svg("circle", { r: r, fill: "#F0A63A", stroke: "#0E1116", "stroke-width": r * 0.12 }, inner);
      const tx = VID.svg("text", { "text-anchor": "middle", "dominant-baseline": "central", "font-size": r * 1.15, "font-weight": 600, fill: "#0E1116", "font-family": "VID Mono, monospace" }, inner);
      tx.textContent = String(n);
      return inner;
    },

    /* Scene fade at both ends, so cuts are soft. */
    sceneEnvelope(tl, stage, scene, opts) {
      const d = VID.dur(scene);
      const o = opts || {};
      if (!o.noIn) tl.fromTo(stage, { opacity: 0 }, { opacity: 1, duration: 0.35, ease: "power1.out" }, 0);
      if (!o.noOut) tl.to(stage, { opacity: 0, duration: 0.25, ease: "power1.in" }, d - 0.27);
      /* keep the timeline as long as the scene */
      tl.set({}, {}, d);
    },
  };

  window.VID = VID;
})();
