/* Agent Plugins tutorial — theme toggle, syntax highlighting, copy buttons, TOC scrollspy.
   No dependency. No network request. */
(function () {
  "use strict";

  // --- theme -------------------------------------------------------------
  var root = document.documentElement;
  var saved = null;
  try { saved = localStorage.getItem("ap-theme"); } catch (e) { /* private mode */ }
  if (saved === "dark" || saved === "light") root.setAttribute("data-theme", saved);

  function currentTheme() {
    var set = root.getAttribute("data-theme");
    if (set) return set;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  function paintToggle(btn) { btn.textContent = currentTheme() === "dark" ? "Light" : "Dark"; }

  var toggle = document.getElementById("theme-toggle");
  if (toggle) {
    paintToggle(toggle);
    toggle.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("ap-theme", next); } catch (e) { /* ignore */ }
      paintToggle(toggle);
    });
  }

  // --- syntax highlighting ----------------------------------------------
  // One combined pattern per language. Strings and comments live in the SAME
  // alternation, so a "//" inside a string never becomes a comment.
  var TS_KW = /^(?:import|export|from|const|let|var|function|return|if|else|for|of|in|while|throw|new|class|extends|interface|type|implements|try|catch|finally|typeof|instanceof|async|await|as|readonly|public|private|static|null|undefined|true|false|this|void|string|number|boolean|unknown|never|Record|Set|Array)$/;
  var PY_KW = /^(?:def|class|return|if|elif|else|for|while|in|not|and|or|is|None|True|False|import|from|as|with|try|except|finally|raise|lambda|yield|pass|continue|break|global|assert|del|print)$/;

  var PATTERNS = {
    json: {
      re: /((?<!\\)\/\/[^\n]*)|("(?:\\.|[^"\\])*")(\s*:)?|(\b-?\d+(?:\.\d+)?\b)|\b(true|false|null)\b/g,
      map: function (m) {
        if (m[1]) return ["tok-com", m[1]];
        if (m[2]) return [m[3] ? "tok-key" : "tok-str", m[2] + (m[3] || "")];
        if (m[4]) return ["tok-num", m[4]];
        return ["tok-kw", m[5]];
      }
    },
    ts: {
      re: /((?<!\\)\/\/[^\n]*|\/\*[\s\S]*?\*\/)|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)|(\b-?\d+(?:\.\d+)?\b)|([A-Za-z_$][\w$]*)/g,
      map: function (m) {
        if (m[1]) return ["tok-com", m[1]];
        if (m[2]) return ["tok-str", m[2]];
        if (m[3]) return ["tok-num", m[3]];
        return TS_KW.test(m[4]) ? ["tok-kw", m[4]] : [null, m[4]];
      }
    },
    python: {
      re: /(#[^\n]*)|("""[\s\S]*?"""|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(\b-?\d+(?:\.\d+)?\b)|([A-Za-z_][\w]*)/g,
      map: function (m) {
        if (m[1]) return ["tok-com", m[1]];
        if (m[2]) return ["tok-str", m[2]];
        if (m[3]) return ["tok-num", m[3]];
        return PY_KW.test(m[4]) ? ["tok-kw", m[4]] : [null, m[4]];
      }
    }
  };
  PATTERNS.jsonc = PATTERNS.json;
  PATTERNS.js = PATTERNS.ts;

  function esc(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function highlight(text, lang) {
    var p = PATTERNS[lang];
    if (!p) return esc(text);
    var out = "";
    var last = 0;
    var m;
    p.re.lastIndex = 0;
    while ((m = p.re.exec(text)) !== null) {
      var pair = p.map(m);
      out += esc(text.slice(last, m.index));
      out += pair[0] ? '<span class="' + pair[0] + '">' + esc(pair[1]) + "</span>" : esc(pair[1]);
      last = m.index + m[0].length;
      if (m[0].length === 0) p.re.lastIndex++;
    }
    return out + esc(text.slice(last));
  }

  Array.prototype.forEach.call(document.querySelectorAll(".code"), function (block) {
    var code = block.querySelector("code");
    if (!code) return;
    var lang = (block.getAttribute("data-lang") || "").toLowerCase();
    var source = code.textContent;
    if (PATTERNS[lang]) code.innerHTML = highlight(source, lang);

    var btn = block.querySelector(".copy");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var done = function () {
        btn.textContent = "copied";
        setTimeout(function () { btn.textContent = "copy"; }, 1400);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(source).then(done, function () { btn.textContent = "failed"; });
      } else {
        var ta = document.createElement("textarea");
        ta.value = source;
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand("copy"); done(); } catch (e) { btn.textContent = "failed"; }
        document.body.removeChild(ta);
      }
    });
  });

  // --- table of contents + scrollspy ------------------------------------
  var toc = document.querySelector(".toc ol");
  if (!toc) return;
  var heads = Array.prototype.slice.call(document.querySelectorAll("main h2[id]"));
  heads.forEach(function (h) {
    var li = document.createElement("li");
    var a = document.createElement("a");
    a.href = "#" + h.id;
    a.textContent = h.textContent.replace(/\s*§[\d.]+\s*$/, "").trim();
    li.appendChild(a);
    toc.appendChild(li);
  });

  var links = Array.prototype.slice.call(toc.querySelectorAll("a"));
  function spy() {
    var best = 0;
    for (var i = 0; i < heads.length; i++) {
      if (heads[i].getBoundingClientRect().top <= 90) best = i;
    }
    links.forEach(function (a, i) { a.classList.toggle("active", i === best); });
  }
  spy();
  var ticking = false;
  window.addEventListener("scroll", function () {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(function () { spy(); ticking = false; });
  }, { passive: true });
})();
