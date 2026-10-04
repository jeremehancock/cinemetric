/* Cinemetric website: small enhancements only. Every piece of content is already in the HTML,
   so the page reads fine if this file never runs. */
(function () {
  "use strict";

  var root = document.documentElement;
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var canObserve = "IntersectionObserver" in window;

  // Turning on the "hidden until revealed" styles only once we know this script runs.
  if (canObserve && !reduceMotion) root.classList.add("js");

  /* ---------- Scroll-in reveals ---------- */
  var reveals = document.querySelectorAll(".reveal");
  // Stagger items that sit side by side (shelf posters, privacy cards, steps).
  document.querySelectorAll(".shelf, .cards, .steps, .hero-inner").forEach(function (group) {
    group.querySelectorAll(".reveal").forEach(function (el, i) {
      el.style.setProperty("--delay", (i * 0.08).toFixed(2) + "s");
    });
  });

  if (root.classList.contains("js")) {
    var revealObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("in");
          revealObserver.unobserve(entry.target);
        }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.12 });
    reveals.forEach(function (el) { revealObserver.observe(el); });
  }

  /* ---------- Header: backdrop after scrolling, highlight current section ---------- */
  var header = document.querySelector(".site-header");
  function onScroll() {
    header.classList.toggle("scrolled", window.scrollY > 24);
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  if (canObserve) {
    var navLinks = {};
    document.querySelectorAll('.nav a[href^="#"]').forEach(function (a) {
      navLinks[a.getAttribute("href").slice(1)] = a;
    });
    // Skill detail sections count as "Skills" in the nav.
    var sectionToNav = function (id) { return id.indexOf("skill-") === 0 ? "skills" : id; };
    var sectionObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var key = sectionToNav(entry.target.id);
        Object.keys(navLinks).forEach(function (k) {
          var on = k === key;
          navLinks[k].classList.toggle("current", on);
          if (on) navLinks[k].setAttribute("aria-current", "true");
          else navLinks[k].removeAttribute("aria-current");
        });
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    document.querySelectorAll("main section[id]").forEach(function (s) { sectionObserver.observe(s); });
    // Clear the highlight while the hero is on screen.
    var hero = document.querySelector(".hero");
    new IntersectionObserver(function (entries) {
      if (entries[0].isIntersecting) {
        Object.keys(navLinks).forEach(function (k) {
          navLinks[k].classList.remove("current");
          navLinks[k].removeAttribute("aria-current");
        });
      }
    }, { rootMargin: "-45% 0px -50% 0px" }).observe(hero);
  }

  /* ---------- Copy buttons ---------- */
  var live = document.getElementById("live");
  var copyIcon = '<svg aria-hidden="true"><use href="#i-copy"/></svg>';
  var checkIcon = '<svg aria-hidden="true"><use href="#i-check"/></svg>';

  function fallbackCopy(text) {
    var area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(area);
    return ok ? Promise.resolve() : Promise.reject(new Error("copy failed"));
  }

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).catch(function () { return fallbackCopy(text); });
    }
    return fallbackCopy(text);
  }

  document.querySelectorAll("button.copy[data-copy]").forEach(function (btn) {
    var timer;
    btn.addEventListener("click", function () {
      var text = btn.getAttribute("data-copy");
      copyText(text).then(function () {
        btn.classList.add("copied");
        btn.innerHTML = checkIcon;
        live.textContent = "Copied: " + text;
      }, function () {
        live.textContent = "Couldn't copy. Select the command and copy it by hand.";
      });
      clearTimeout(timer);
      timer = setTimeout(function () {
        btn.classList.remove("copied");
        btn.innerHTML = copyIcon;
      }, 1800);
    });
  });
})();
