// Progressive enhancements; every page works without this file.
(() => {
  // Put the visitor's platform first in each pair of download buttons.
  const platform = (navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || "";
  if (/mac/i.test(platform) || /Mac OS X/.test(navigator.userAgent)) {
    for (const group of document.querySelectorAll("[data-downloads]")) {
      const win = group.querySelector('[data-os="windows"]');
      const mac = group.querySelector('[data-os="mac"]');
      if (!win || !mac) continue;
      win.classList.remove("btn--solid");
      mac.classList.add("btn--solid");
      group.prepend(mac);
    }
  }

  // Stacked tool screenshots: pointing at a card's zone (the front card's
  // area, or one of the two panel strips) deals that card to the front.
  // Zones are fixed, so a card moving mid-shuffle never retriggers another.
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  for (const wrap of document.querySelectorAll(".stack-wrap")) {
    const stack = wrap.querySelector(".stack");
    const cards = [...wrap.querySelectorAll(".stack__card")];
    const captions = [...wrap.querySelectorAll(".stack__captions li")];
    const edges = [0.73964, 0.86982]; // must match the stack geometry in site.css
    let order = cards.map((_, i) => i); // front to back
    let lifting = null;
    let timer = 0;

    const paint = () => {
      order.forEach((card, depth) => {
        cards[card].style.zIndex = String(cards.length - depth);
      });
      captions.forEach((li, i) => li.classList.toggle("is-front", i === order[0]));
    };

    const settle = () => {
      clearTimeout(timer);
      paint();
      if (lifting) lifting.classList.remove("is-lifting");
      lifting = null;
    };

    const bringToFront = (index) => {
      if (order[0] === index) return;
      settle();
      // the rest keep their natural depth so each panel strip shows its own card
      order = [index, ...cards.map((_, i) => i).filter((i) => i !== index)];
      if (reduceMotion) {
        paint();
        return;
      }
      lifting = cards[index];
      lifting.classList.add("is-lifting");
      timer = setTimeout(settle, 160);
    };

    const zoneAt = (clientX) => {
      const box = stack.getBoundingClientRect();
      const f = (clientX - box.left) / box.width;
      return f < edges[0] ? 0 : f < edges[1] ? 1 : 2;
    };

    wrap.addEventListener("pointermove", (e) => bringToFront(zoneAt(e.clientX)));
    wrap.addEventListener("click", (e) => bringToFront(zoneAt(e.clientX))); // touch
    wrap.addEventListener("pointerleave", () => bringToFront(0));
    cards.forEach((card, i) => card.addEventListener("focus", () => bringToFront(i)));
    paint();
  }
})();
