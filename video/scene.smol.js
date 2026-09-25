// smol.js — "smol-sim-search", a 100.25 s VO-driven short.
// Storyboard: STORYBOARD.md. Audio: vo/voiceover.wav (timings in vo/timings.json).
(() => {
  // ---------- palette for this film ----------
  const COOL = mixCol(PAL.sky, PAL.paper, .45);       // hook: confused grey-blue
  const WARM = mixCol(PAL.cream, PAL.rose, .25);      // meet/install
  const SAND = '#EFD9A7', WOOD = '#C89B6B', WOODD = '#B3865A';
  const FAM = [PAL.clay, PAL.teal, PAL.ochre];        // the three meaning families

  // ---------- set pieces ----------
  // A hand-painted file card. o: {doodle:'fish'|'star', cross:0..1, splot:0..1, lines:int}
  function card(x, y, w, rot, key, o = {}) {
    boilSeed('card' + key);
    const h = w * 1.28;
    push(); translate(x, y); rotate(rot);
    paint(rrPts(-w / 2, -h / 2, w, h, w * .12, 1.5), { wash: PAL.cream, ink: PAL.ink, sw: Math.max(.5, w * .012) });
    const n = o.lines ?? 3;
    for (let i = 0; i < n; i++) {                     // scribble "words": wobbly strokes, never letters
      const ly = -h * .28 + i * h * .2, lw = w * (.62 - .13 * hash(key * 7 + i));
      inkLine([[-w * .32, ly], [-w * .32 + lw * .45, ly + jit(1.5)], [-w * .32 + lw, ly + jit(1.5)]],
              Math.max(.5, w * .016), mixCol(PAL.ink, PAL.cream, .25), 'inkfine', .5);
    }
    if (o.doodle === 'fish') {                        // the MEANING, drawn: a tiny fish
      const s = w * .16, fx = w * .2, fy = h * .34;
      paint(ellPts(fx, fy, s, s * .55, 12, .5), { wash: PAL.teal, ink: PAL.ink, sw: .5 });
      paint([[fx - s * .8, fy], [fx - s * 1.5, fy - s * .5], [fx - s * 1.5, fy + s * .5]], { wash: PAL.teal, ink: PAL.ink, sw: .5 });
      paint(ellPts(fx + s * .45, fy - s * .12, s * .09, s * .09, 6), { wash: PAL.ink, ink: null });
    } else if (o.doodle === 'star') {
      paint(starPts(w * .2, h * .34, w * .14, .45, 5), { wash: PAL.ochre, ink: PAL.ink, sw: .5 });
    }
    if (o.splot) paint(ellPts(-w * .18, h * .3, w * .13 * o.splot, w * .1 * o.splot, 10, 2), { wash: PAL.indigo, ink: null });
    if (o.cross) {                                    // the red-ink NOPE
      const k = clamp(o.cross), c = mixCol(PAL.rose, PAL.ink, .25), sw2 = Math.max(1.2, w * .045);
      const e1 = Math.min(1, k * 2), e2 = (k - .5) * 2;
      if (k > 0) inkLine([[-w * .38, -h * .38], [lerp(-w * .38, w * .38, e1 * .5) + jit(2), lerp(-h * .38, h * .38, e1 * .5)], [lerp(-w * .38, w * .38, e1), lerp(-h * .38, h * .38, e1)]], sw2, c, 'ink', .3);
      if (k > .5) inkLine([[w * .38, -h * .38], [lerp(w * .38, -w * .38, e2 * .5) + jit(2), lerp(-h * .38, h * .38, e2 * .5)], [lerp(w * .38, -w * .38, e2), lerp(-h * .38, h * .38, e2)]], sw2, c, 'ink', .3);
    }
    pop();
  }

  // A meaning-dot. o: {glowK, eyes, lookX, blink}
  function dot(x, y, r, col, key, o = {}) {
    boilSeed('dot' + key);
    if (o.glowK) glow(x, y, r * 6, col, .5 * o.glowK);
    paint(ellPts(x, y, r, r, 14, .8), { wash: col, ink: PAL.ink, sw: Math.max(.5, r * .1) });
    if (o.eyes) {
      const e = r * .28, dx = r * .34, lx = (o.lookX ?? 0) * r * .14;
      for (const s of [-1, 1]) {
        paint(ellPts(x + s * dx + lx, y - r * .15, e, o.blink ? e * .1 : e * 1.4, 8), { wash: PAL.cream, ink: null });
        if (!o.blink) paint(ellPts(x + s * dx + lx * 1.6, y - r * .15, e * .4, e * .55, 6), { wash: PAL.ink, ink: null });
      }
    }
  }

  // The wooden crate (the repo). o: {lid: 0..1 open, label}
  function crate(x, y, w, key, o = {}) {                 // (x, y) = ground centre
    boilSeed('crate' + key);
    const h = w * .62;
    paint(ellPts(x, y + 4, w * .62, 9, 16, 2), { wash: PAL.ink, washOp: 26, ink: null });
    paint(rrPts(x - w / 2, y - h, w, h, 6, 2), { wash: WOOD, ink: PAL.ink, sw: 1.1 });
    for (const k of [-.17, .17]) inkLine([[x - w / 2 + 6, y - h / 2 + k * h], [x + w / 2 - 6, y - h / 2 + k * h]], .8, WOODD, 'inkfine');
    inkLine([[x - w / 2 + 5, y - h + 7], [x + w / 2 - 5, y - h + 7]], 2.2, WOODD, 'ink');
    if (o.lid !== undefined) {                           // hinged lid, hinge at back-left
      push(); translate(x - w / 2, y - h); rotate(-o.lid * 2.2);
      paint(rrPts(0, -w * .1, w, w * .1, 3, 1.5), { wash: WOODD, ink: PAL.ink, sw: 1 });
      pop();
    }
    if (o.label) { boilSeed('crlab' + key); paint(ellPts(x, y - h * .5, w * .13, w * .13, 12, 1), { wash: PAL.cream, ink: PAL.ink, sw: .8 }); lensDoodle(x, y - h * .5, w * .09); }
  }
  function lensDoodle(x, y, r) {
    paint(ellPts(x - r * .2, y - r * .2, r, r, 12, .5), { wash: '#DDEDF5', ink: PAL.ink, sw: Math.max(.6, r * .12) });
    inkLine([[x + r * .5, y + r * .5], [x + r * 1.2, y + r * 1.2]], Math.max(.8, r * .2), PAL.ink);
  }

  // The magnifying lens, drawn at the arm tip (arm space: +x outward). k01 = dots visible.
  function lensProp(dotsK = 0) {
    return (u, sw) => {
      const r = u * 1.8;
      inkLine([[0, 0], [r * .72, 0]], Math.max(1.4, u * .22), PAL.ink);           // handle from the claw
      paint(ellPts(r * 1.5, 0, r, r, 22, .6), { wash: '#DDEDF5', washOp: 245, ink: PAL.ink, sw: Math.max(1, u * .13) });
      inkLine([[r * 1.05, -r * .42], [r * 1.38, -r * .6]], Math.max(1, u * .12), PAL.cream, 'ink', .4);
      if (dotsK > 0) {
        const dd = [[-.28, -.22, FAM[0]], [.3, .02, FAM[1]], [-.04, .34, FAM[2]]];
        for (let i = 0; i < 3; i++) {
          const [ox, oy, c] = dd[i], k = clamp(dotsK * 3 - i);
          if (k > 0) paint(ellPts(r * 1.5 + ox * r, oy * r, r * .17 * backOut(k), r * .17 * backOut(k), 10), { wash: c, ink: null });
        }
      }
    };
  }

  // Down-arrow rain cloud (the download that never happens). s = size, k = alive 0..1
  function cloud(x, y, s, k, t) {
    if (k <= 0) return;
    boilSeed('cloud');
    push(); translate(x, y); scale(k);
    const g = mixCol(PAL.indigo, PAL.cream, .55);
    for (const [ox, oy, r] of [[-s * .5, 0, s * .42], [0, -s * .28, s * .55], [s * .5, 0, s * .45], [0, .08 * s, s * .5]])
      paint(ellPts(ox, oy, r, r * .8, 14, 2), { wash: g, ink: null });
    paint(ellPts(0, 0, s * 1.05, s * .55, 18, 3), { wash: g, ink: PAL.ink, sw: 1 });
    const bob = 4 * Math.sin(t * 3);
    paint([[-s * .16, s * .62 + bob], [s * .16, s * .62 + bob], [s * .16, s * .95 + bob], [s * .34, s * .95 + bob], [0, s * 1.3 + bob], [-s * .34, s * .95 + bob], [-s * .16, s * .95 + bob]],
          { wash: PAL.sky, ink: PAL.ink, sw: 1 });
    pop();
  }

  function poof(x, y, s, k) {                            // k 0..1: expanding puffs
    if (k <= 0 || k >= 1) return;
    boilSeed('poof' + ((x * 7 + y) | 0));
    for (let i = 0; i < 6; i++) {
      const a = i / 6 * TAU + hash(i) * .8, d = s * (0.4 + 1.1 * ease(k));
      paint(ellPts(x + Math.cos(a) * d, y + Math.sin(a) * d * .7, s * .22 * (1 - k), s * .2 * (1 - k), 8, 1), { wash: PAL.cream, washOp: 210 * (1 - k), ink: null });
    }
  }

  // Retro handset phone. o: {ring 0..1, droop 0..1}
  function phone(x, y, s, o = {}) {
    boilSeed('phone');
    push(); translate(x, y); rotate((o.ring ? .09 * Math.sin(T * 40) : 0) + (o.droop || 0) * .35);
    paint(ellPts(0, 3, s * .95, s * .2, 12, 1), { wash: PAL.ink, washOp: 24, ink: null });
    paint(rrPts(-s * .55, -s * .5, s * 1.1, s * .5, s * .12, 1), { wash: PAL.night, ink: PAL.ink, sw: 1 });   // base
    paint(ellPts(0, -s * .28, s * .18, s * .18, 10), { wash: PAL.cream, ink: PAL.ink, sw: .7 });              // dial
    const hy = -s * .62 + (o.droop || 0) * s * .18;
    paint(rrPts(-s * .62, hy - s * .16, s * 1.24, s * .2, s * .1, 1), { wash: PAL.night, ink: PAL.ink, sw: 1 }); // handset bar
    for (const q of [-1, 1]) paint(ellPts(q * s * .55, hy - s * .08, s * .17, s * .2, 10), { wash: PAL.night, ink: PAL.ink, sw: 1 });
    pop();
  }

  function flag(x, y, s, plant) {                        // plant 0..1: arcs down, then wobbles
    if (plant <= 0) return;
    const p = ease(Math.min(1, plant * 1.4)), wobK = spring(plant, 1 / 1.4, .12, 9);
    const gy = lerp(y - 220, y, p);
    push(); translate(x, gy); rotate(wobK * .4);
    inkLine([[0, 0], [0, -s]], Math.max(1.4, s * .05), PAL.ink);
    paint([[0, -s], [s * .62, -s * .8], [0, -s * .6]], { wash: PAL.rose, ink: PAL.ink, sw: 1 });
    pop();
  }

  function pail(x, y, s, fillK, t) {
    boilSeed('pail');
    paint(ellPts(x, y + 2, s * .75, s * .16, 12, 1), { wash: PAL.ink, washOp: 25, ink: null });
    paint([[x - s * .55, y - s], [x + s * .55, y - s], [x + s * .42, y], [x - s * .42, y]], { wash: PAL.teal, ink: PAL.ink, sw: 1.2 });
    paint(ellPts(x, y - s, s * .55, s * .12, 14, 1), { wash: mixCol(PAL.teal, PAL.ink, .25), ink: PAL.ink, sw: 1 });
    if (fillK > 0) {                                     // the collected meaning-dots
      for (let i = 0; i < 7; i++) { if (fillK * 7 > i) { boilSeed('paildot' + i);
        paint(ellPts(x - s * .3 + hash(i) * s * .6, y - s - 3 - hash(i + 9) * 6, 4.5, 4.5, 8), { wash: FAM[i % 3], ink: PAL.ink, sw: .5 }); } }
    }
    inkLine(ellPts(x, y - s * .9, s * .58, s * .5, 16).slice(8, 17), Math.max(1.2, s * .05), PAL.ink, 'ink', .8);  // handle
  }

  function starfish(x, y, s) { boilSeed('strf'); paint(starPts(x, y, s, .5, 5, .3), { wash: PAL.ochre, ink: PAL.ink, sw: 1 }); }

  function sandbox(t, skyK = 0) {                        // the logo scene. skyK darkens toward dusk
    boilSeed('sbsky');
    paint(rectPts(-600, -400, W + 1200, H + 800), { wash: mixCol(WARM, PAL.indigo, .55 * skyK), ink: null });
    boilSeed('sbsun');
    if (skyK < .5) glow(W * .8, 180, 260, PAL.ochre, .5 * (1 - skyK * 2));
    boilSeed('sbsand');
    paint(ellPts(960, 780, 640, 110, 30, 4), { wash: SAND, fill: mixCol(SAND, PAL.ochre, .5), fillOp: 55, bleed: .12, tex: .5, ink: PAL.ink, sw: 1 });
    boilSeed('sbfloor');
    paint(rectPts(-600, 852, W + 1200, 600), { wash: mixCol(PAL.sap, PAL.cream, .55), ink: null });
  }
  function sandboxFrame() {
    boilSeed('sbframe');
    paint(rrPts(300, 800, 1320, 92, 12, 2), { wash: WOOD, ink: PAL.ink, sw: 1.4 });
    paint(rrPts(300, 800, 1320, 26, 10, 2), { wash: WOODD, ink: null });
  }

  // ---------- shared layouts ----------
  const NC = 12;                                          // the twelve cards / dots
  const fam = i => i % 3;
  const gridPos = i => [700 + (i % 4) * 170, 420 + ((i / 4) | 0) * 170];
  const HUD = [[640, 400], [1210, 300], [1010, 640]];     // huddle centres (world, shot E/F/G)
  const hudPos = (i, spread = 1) => {
    const c = HUD[fam(i)], a = hash(i * 13) * TAU, r = (34 + 66 * hash(i * 7 + 2)) * spread;
    return [c[0] + Math.cos(a) * r, c[1] + Math.sin(a) * r * .8];
  };
  const OUTLIER = [255, 825];                             // the lonely dot

  // ============================================================ A: the grep problem
  function shotA(t, lt, dur) {
    camBegin(960 + 12 * Math.sin(lt * .35), 540 + 6 * Math.sin(lt * .5 + 2), 1 + .012 * lt);
    boilSeed('Abg');
    paint(rectPts(-600, -400, W + 1200, H + 800), { wash: COOL, ink: null });
    paint(ellPts(900, 1120, 1500, 420, 30, 6), { fill: mixCol(COOL, PAL.indigo, .3), fillOp: 60, bleed: .2, tex: .5, ink: null });

    // drifting file cards (the repo)
    for (let i = 0; i < 9; i++) {
      if (i === 3 || i === 6) continue;                                   // reserved for the two compares
      const x = 180 + hash(i) * 1560 + 26 * Math.sin(lt * .3 + i * 1.7);
      const y = 150 + hash(i + 40) * 420 + 16 * Math.sin(lt * .42 + i);
      card(x, y, 92 + 40 * hash(i + 80), .12 * Math.sin(i * 9 + lt * .2), i, { lines: 3 });
    }
    // compare #1 and #2: cards drift in to the lens, get the X, drift off
    const c1 = kf(lt, [[2.6, [-160, 430]], [4.2, [700, 430]], [6.2, [700, 430]], [7.4, [640, 1260]]], ease);
    card(c1[0], c1[1], 130, .06 * Math.sin(lt), 103, { doodle: 'star', cross: seg(lt, 5.0, 5.9) });
    const c2 = kf(lt, [[5.8, [2080, 380]], [7.3, [710, 400]], [9.2, [710, 400]], [10.2, [780, -260]]], ease);
    card(c2[0], c2[1], 130, -.05 * Math.sin(lt * 1.2), 106, { lines: 4, cross: seg(lt, 8.2, 9.1) });
    // the synonym drifts by BEHIND Clawd: same fish, different scribbles. Clawd never sees it.
    const sx = kf(lt, [[8.8, [2120, 800]], [12.6, [660, 815]], [14.2, [430, 830]]], ease);
    card(sx[0], sx[1], 118, -.08, 111, { doodle: 'fish', lines: 2 });

    // Clawd, hunting by exact match: bored -> focused squint -> denial -> gloom
    const mood = emotions(lt, [[0, 'bored'], [2.8, 'thinking', { lookX: -.6, lookY: -.3 }],
      [4.6, 'suspicious', { lookX: -.5 }], [7.6, 'suspicious', { lookX: -.35, lookY: -.2 }], [11.3, 'confused']]);
    const shake = ring(lt, [5.45, 8.65]);
    clawd(1150, 900, 26, { ...mood, rot: shake * .1, aR: kf(lt, [[0, .2], [3.4, .95], [11.5, .95], [12.6, .1]], ease), armR: lensProp(0), aL: -.4, flip: true });
    // its own little want-card, held up on the left arm side
    card(1352, 668 + mood.dy * 3 + 7 * Math.sin(lt * 1.7), 84, .1 + shake * .06, 120, { doodle: 'fish', lines: 2 });

    camEnd();
    if (lt < .5) iris(1150, 800, lerp(0, 1600, easeIn(lt / .5)), PAL.paper);
    if (lt > dur - .35) brushWipe((lt - (dur - .35)) / .7, [PAL.clay, PAL.rose]);
  }

  // ============================================================ B: meet smol-sim-search
  function shotB(t, lt, dur) {
    camBegin(960, 540 - 8 * Math.sin(lt * .4), 1.02 + .01 * Math.sin(lt * .5));
    boilSeed('Bbg');
    paint(rectPts(-600, -400, W + 1200, H + 800), { wash: WARM, ink: null });
    paint(ellPts(960, 300, 900, 420, 26, 8), { fill: PAL.rose, fillOp: 42, bleed: .25, tex: .5, ink: null });
    paint(ellPts(900, 1140, 1500, 430, 30, 6), { fill: PAL.ochre, fillOp: 46, bleed: .18, tex: .5, ink: null });
    for (let i = 0; i < 10; i++) {                       // celebratory drifting specks
      boilSeed('spk' + i);
      const k = frac(lt * .12 + hash(i));
      paint(ellPts(120 + hash(i) * 1700, 1100 - k * 900, 5 + 4 * hash(i + 3), 5 + 4 * hash(i + 3), 8), { wash: FAM[i % 3], washOp: 170 * Math.sin(k * Math.PI), ink: null });
    }

    // the crate slides in, Clawd hops behind it (lives IN the repo)
    const cx = kf(lt, [[4.2, 2350], [5.8, 1210]], backOut);
    const hop = jump(lt, 6.3, 7.0, 7);
    const inCrate = lt > 6.65;
    const mood = emotions(lt, [[0, 'surprised'], [1.1, 'excited'], [6.9, 'happy'], [7.8, 'proud']]);
    const cy2 = inCrate ? 912 : 900;
    if (!inCrate) {
      clawd(kf(lt, [[6.2, 830], [7.0, 1140]], ease), cy2, 24, { ...mood, dy: mood.dy + hop.dy, sq: mood.sq + hop.sq });
      crate(cx, 940, 300, 'B');
    } else {
      // peeking out: draw Clawd sunk, then the crate front over the legs
      clawd(1195, cy2, 24, { ...mood, dy: mood.dy + hop.dy + .8, sq: mood.sq + hop.sq, noShadow: true,
        aR: kf(lt, [[7.4, -.4], [8.3, 1.25]], backOut), armR: lensProp(seg(lt, 8.6, 10.2)), lookX: kf(lt, [[8.2, 0], [8.8, .55]], ease) });
      crate(cx, 940, 300, 'B');
    }

    camEnd();
    // the title, sailing in on the beat
    const tp = seg(lt, 1.9, 3.0), thold = 1 - seg(lt, 9.9, 10.8);
    if (tp > 0 && thold > 0)
      letter('smol-sim-search', 960, 250, 108, PAL.clay, { pop: backOut(tp), rot: -.03 + .05 * tp, alpha: 255 * Math.min(1, tp * 3) * thold });
    if (lt < .35) brushWipe(.5 + lt / .7, [PAL.clay, PAL.rose]);
    if (lt > dur - .12) flash(seg(lt, dur - .12, dur) * .8, PAL.cream);
  }

  // ============================================================ C: install
  function shotC(t, lt, dur) {
    camBegin(960 + kf(lt, [[8.7, 0], [9.6, 150]], ease), 560, 1.03 + .012 * Math.sin(lt * .45));
    boilSeed('Cbg');
    paint(rectPts(-600, -400, W + 1200, H + 800), { wash: mixCol(PAL.cream, PAL.ochre, .16), ink: null });
    paint(rectPts(-600, 902, W + 1200, 600), { wash: mixCol(PAL.sap, PAL.cream, .5), ink: null });
    inkLine([[300, 905], [960, 907], [1620, 905]], 1.4, mixCol(PAL.ink, PAL.cream, .3), 'ink', .4);
    paint(ellPts(1500, 250, 380, 200, 20, 8), { fill: PAL.rose, fillOp: 30, bleed: .25, tex: .5, ink: null });

    // crate 1, and its clone stamping out of it
    crate(560, 900, 280, 'C1');
    const ck = seg(lt, 1.2, 2.3);
    if (ck > 0) {
      const nx = lerp(560, 940, backOut(ck)), land = spring(lt, 2.3, .1, 8);
      crate(nx, 900 - 60 * Math.sin(Math.PI * Math.min(1, ck)) + 0 * land, 280, 'C2', { lid: kf(lt, [[8.2, 0], [9.0, 1]], backOut) });
      poof(750, 880, 60, seg(lt, 1.35, 2.1));
    }
    // the big lever on crate 2
    if (ck > .55) {
      boilSeed('lever');
      const la = kf(lt, [[2.9, -.9], [4.0, -.9], [4.55, .75]], easeIn), wobK2 = spring(lt, 4.55, .15, 7);
      push(); translate(1120, 862); rotate(la + wobK2 * .3);
      inkLine([[0, 0], [0, -128]], 10, PAL.ink); paint(ellPts(0, -140, 24, 24, 12), { wash: PAL.rose, ink: PAL.ink, sw: 1.6 });
      pop();
    }
    // parts arc out of the opened crate and land on the floor
    const parts = [[1240, 'gear', PAL.teal], [1460, 'lens', null], [1600, 'bat', PAL.sap], [1720, 'bat', PAL.sap]];
    parts.forEach(([tx, kind, col], i) => {
      const p = seg(lt, 9.0 + i * .28, 9.95 + i * .28);
      if (p <= 0) return;
      const [px, py] = arcPt([940, 740], [tx, 856], 210 + 30 * i, ease(p));
      const w2 = spring(lt, 9.95 + i * .28, .12, 9), bop = kind === 'bat' ? Math.abs(7 * pulse(t, 2)) * seg(lt, 10.9, 11.5) : 0;
      boilSeed('part' + i);
      push(); translate(px, py - bop); rotate(p < 1 ? p * 2.5 : w2 * .35);
      if (kind === 'gear') {
        for (let k2 = 0; k2 < 8; k2++) { const a = k2 / 8 * TAU; paint(rectPts(Math.cos(a) * 50 - 9, Math.sin(a) * 50 - 9, 18, 18, .5), { wash: col, ink: PAL.ink, sw: 1 }); }
        paint(ellPts(0, 0, 47, 47, 16), { wash: col, ink: PAL.ink, sw: 1.6 }); paint(ellPts(0, 0, 15, 15, 10), { wash: PAL.cream, ink: PAL.ink, sw: 1 });
      } else if (kind === 'lens') { lensDoodle(0, -10, 38); }
      else { paint(rrPts(-20, -50, 40, 90, 8, 1), { wash: col, ink: PAL.ink, sw: 1.5 }); paint(rrPts(-9, -61, 18, 12, 3, .5), { wash: PAL.ink, ink: null });
             inkLine([[-9, -12], [9, -12]], 3, PAL.cream); inkLine([[0, -21], [0, -3]], 3, PAL.cream); }
      pop();
    });

    // the download cloud: in, shooed, gone
    const ckin = seg(lt, 5.4, 6.1), cko = seg(lt, 7.0, 7.45);
    cloud(kf(lt, [[5.4, 2150], [6.1, 1560], [7.0, 1560], [7.45, 1980]], ease), 300, 95, (1 - cko) * Math.min(1, ckin * 3), lt);
    poof(1900, 320, 90, seg(lt, 7.35, 7.95));

    // Clawd: conducts the whole thing
    const mood = emotions(lt, [[0, 'happy', { lookX: -.5 }], [1.15, 'surprised', { lookX: -.2 }], [2.6, 'mischief'],
      [3.1, 'determined', { lookX: .3 }], [4.9, 'suspicious', { lookX: .8, lookY: -.5 }],
      [6.0, 'angry', { lookX: .85, lookY: -.5 }], [7.4, 'relieved'], [8.3, 'determined', { lookX: .4, lookY: -.2 }],
      [9.8, 'proud', { lookX: .5 }], [11.4, 'happy', { lookX: .3 }]]);
    const shooA = lt > 6.0 && lt < 7.4 ? .9 + .55 * Math.sin(lt * 13) : (lt > 3.1 && lt < 4.7 ? -.35 : .25);
    clawd(kf(lt, [[0, 780], [2.9, 780], [3.6, 1210], [5.5, 1210], [6.0, 1080], [10.8, 1080], [11.6, 1360], [12.8, 1360]], ease), 902, 23,
          { ...mood, aR: kf(lt, [[2.9, .2], [3.8, -.55], [4.3, -.55], [4.7, .5], [6.0, shooA]], ease), aL: -.3,
            view: lt > 2.9 && lt < 3.6 ? 'q' : 'front', walk: lt > 2.9 && lt < 3.6 ? lt * 9 : (lt > 11.0 && lt < 11.6 ? lt * 9 : 0) });

    camEnd();
    const dp = seg(lt, 7.3, 8.0), dh = 1 - seg(lt, 9.2, 9.8);
    if (dp > 0) letter('0 DOWNLOADS', 1560, 300, 84, PAL.teal, { pop: backOut(dp), rot: .06 - .1 * dp, alpha: 255 * Math.min(1, dp * 3) * dh });
    if (lt < .2) flash((1 - lt / .2) * .8, PAL.cream);
  }

  // ============================================================ D: any repo, self-indexing
  function shotD(t, lt, dur) {
    const inside = lt >= 5.1;
    if (!inside) {
      // the street of repo-doors; whip-pan settle at the start
      const wx = kf(lt, [[0, 560], [.45, 0]], easeOut);
      camBegin(960 + wx, 540, 1.04);
      boilSeed('Dbg');
      paint(rectPts(-800, -400, W + 1600, H + 800), { wash: mixCol(PAL.sky, PAL.cream, .55), ink: null });
      paint(rectPts(-800, 872, W + 1600, 600), { wash: mixCol(PAL.sap, PAL.cream, .42), ink: null });
      inkLine([[240, 875], [960, 877], [1680, 875]], 1.4, mixCol(PAL.ink, PAL.cream, .3), 'ink', .4);
      const cols = [PAL.rose, PAL.sap, PAL.teal, PAL.ochre, PAL.violet];
      for (let i = 0; i < 5; i++) {
        boilSeed('door' + i);
        const dx = 260 + i * 350, sel = i === 2;
        paint(rrPts(dx - 95, 560, 190, 315, 60, 2), { wash: mixCol(cols[i], PAL.cream, .25), ink: PAL.ink, sw: 1.6 });
        paint(ellPts(dx + 58, 740, 9, 9, 8), { wash: PAL.ink, ink: null });
        if (sel) lensDoodle(dx, 640, 26);
      }
      if (lt > .4) {                                     // the trot, in profile
        const st = stroll(lt, .5, 3.3, 240, 890, 22);
        const mood2 = emotions(lt, [[0, 'hopeful'], [3.3, 'happy', { lookY: -.4 }], [4.4, 'idea']]);
        clawd(st.x, 872, 22, { ...mood2, view: lt < 3.3 ? 'side' : 'front', walk: st.walk, dy: st.dy });
      } else {
        clawd(240, 872, 22, { ...feel('hopeful', t), view: 'side', smear: .7, smearDir: 1 });
      }
      const doorX = 960;                                  // door #2 opens as an iris into the room
      camEnd();
      if (lt > 4.5) { const k = seg(lt, 4.5, 5.1); irisShape(rrPts(doorX - 95 - 700 * k, 560 - 560 * k, 190 + 1400 * k, 315 + 1000 * k, 60, 2), PAL.ink); }
      if (lt < .45) { boilSeed('smearD'); for (let i = 0; i < 7; i++) { const sx0 = 200 + hash(i) * 1500 + 300 * (1 - lt / .45), sy0 = 200 + hash(i + 5) * 700; inkLine([[sx0, sy0], [sx0 + 180, sy0 + jit(2)], [sx0 + 360, sy0]], 2.5, mixCol(PAL.ink, PAL.cream, .55), 'ink', .3); } }
    } else {
      const llt = lt - 5.1;                               // time inside the room
      camBegin(960, 540, 1.02 + .015 * Math.sin(llt * .5));
      boilSeed('Dint');
      paint(rectPts(-600, -400, W + 1200, H + 800), { wash: mixCol(PAL.indigo, PAL.cream, .72), ink: null });
      paint(rectPts(-600, 942, W + 1200, 600), { wash: mixCol(PAL.indigo, PAL.cream, .58), ink: null });
      // twelve messy cards swirl, then snap to the grid on a beat
      for (let i = 0; i < NC; i++) {
        const mess = [240 + hash(i) * 1440, 220 + hash(i + 30) * 560];
        const swirlA = hash(i * 3) * TAU + llt * (1.1 + hash(i)), swirlR = lerp(1, .55, seg(llt, 0, 1.6));
        const sw2 = [960 + Math.cos(swirlA) * (mess[0] - 960) * swirlR - Math.sin(swirlA) * 26, 480 + Math.sin(swirlA * .8) * (mess[1] - 480) * swirlR];
        const snapK = backOut(seg(llt, 1.6 + hash(i) * .5, 2.5 + hash(i) * .5));
        const p = [lerp(sw2[0], gridPos(i)[0], snapK), lerp(sw2[1], gridPos(i)[1], snapK)];
        const changed = i === 6, wig = changed ? .16 * Math.sin(llt * 21) * seg(llt, 3.1, 3.5) * (1 - seg(llt, 4.6, 5)) : 0;
        card(p[0], p[1], 96, wig + (snapK < 1 ? Math.sin(swirlA) * .18 * (1 - snapK) : .02 * Math.sin(i + llt * .5)), 300 + i,
             { lines: 2 + (i % 2), splot: changed ? seg(llt, 3.0, 3.3) * (1 - seg(llt, 4.35, 4.8)) : 0 });
        if (changed) {                                    // the single re-scan ping
          const ping = seg(llt, 3.9, 4.5);
          if (ping > 0 && ping < 1) { glow(p[0], p[1], 150, PAL.teal, .7 * Math.sin(ping * Math.PI)); inkLine(ellPts(p[0], p[1], 88 * ping + 30, 108 * ping + 36, 22).concat([ellPts(p[0], p[1], 88 * ping + 30, 108 * ping + 36, 22)[0]]), 2.2 * (1 - ping) + .6, PAL.teal, 'ink', 1); }
          if (llt > 4.6) emote('spark', p[0] + 60, p[1] - 74, 15, Math.min(1, (llt - 4.6) * 3), llt);
        }
      }
      const mood3 = emotions(llt, [[0, 'thinking', { lookY: -.35 }], [2.2, 'surprised', { lookY: -.3 }], [3.0, 'thinking', { lookX: .25, lookY: -.2 }], [4.6, 'happy', { lookY: -.25 }]]);
      clawd(400, 950, 21, mood3);
      camEnd();
      if (llt < .45) { const k = 1 - seg(llt, 0, .45); if (k > 0) irisShape(rrPts(960 - 95 - 700 * (1 - k), 560 - 560 * (1 - k), 190 + 1400 * (1 - k), 315 + 1000 * (1 - k), 60, 2), PAL.ink); }
    }
  }

  // ============================================================ E: meaning space
  function shotE(t, lt, dur) {
    const dark = seg(lt, 0, 2.2);
    const push_ = seg(lt, 7.2, 11.5);
    camBegin(lerp(960, 700, ease(push_)), lerp(540, 430, ease(push_)), 1 + .42 * ease(push_));
    boilSeed('Ebg');
    paint(rectPts(-800, -500, W + 1600, H + 1000), { wash: mixCol(mixCol(PAL.indigo, PAL.cream, .72), PAL.night, .88 * dark), ink: null });
    if (dark > .4) { boilSeed('Eneb'); paint(ellPts(600, 300, 500, 320, 22, 10), { fill: PAL.violet, fillOp: 40 * dark, bleed: .3, tex: .5, ink: null }); paint(ellPts(1400, 700, 520, 300, 22, 10), { fill: PAL.indigo, fillOp: 46 * dark, bleed: .3, tex: .5, ink: null }); }
    for (let i = 0; i < 26; i++) { boilSeed('Est' + i); const tw = .5 + .5 * Math.sin(lt * (1.5 + hash(i)) + i * 2); paint(starPts(hash(i) * W, hash(i + 50) * 560, 3 + 3 * hash(i + 9) * tw, .4, 4), { wash: PAL.cream, washOp: 120 * dark * tw, ink: null }); }

    // cards rise from the grid and become the family dots, then huddle
    for (let i = 0; i < NC; i++) {
      const rise = ease(seg(lt, .2 + hash(i) * .8, 2.6 + hash(i) * .8));
      const hud = ease(seg(lt, 3.4 + hash(i * 5) * .8, 5.8 + hash(i * 5) * .8));
      const g = gridPos(i), up = [g[0] + 30 * Math.sin(i), g[1] - 330 - 140 * hash(i)], hp = hudPos(i);
      const p = [lerp(lerp(g[0], up[0], rise), hp[0], hud), lerp(lerp(g[1], up[1], rise), hp[1], hud)];
      const morph = seg(lt, 1.1 + hash(i) * .9, 1.9 + hash(i) * .9);
      if (morph < 1) card(p[0], p[1], 96 * (1 - morph * .96), .05 * Math.sin(i + lt), 300 + i, { lines: 2 });
      if (morph > .4) dot(p[0], p[1], (10 + 6 * hash(i + 2)) * Math.min(1, (morph - .4) * 2.4), FAM[fam(i)], 500 + i, { glowK: .4 * dark + .5 * push_ });
    }
    // the neighborhood ring, read through the lens
    const ringK = seg(lt, 8.6, 9.6);
    if (ringK > 0) { boilSeed('Ering'); const rr = 150 + 12 * pulse(t, 1.2); inkLine(ellPts(HUD[0][0], HUD[0][1], rr, rr * .84, 30).concat([ellPts(HUD[0][0], HUD[0][1], rr, rr * .84, 30)[0]]), 2.4 * ringK, PAL.cream, 'ink', 1); glow(HUD[0][0], HUD[0][1], 230, FAM[0], .5 * ringK); }

    // Clawd on a dark rise, lifting the lens into the shot
    boilSeed('Ehill');
    paint(ellPts(760, 1210, 900, 330, 26, 6), { wash: mixCol(PAL.indigo, PAL.night, .5 * dark), ink: PAL.ink, sw: 1 });
    const moodE = emotions(lt, [[0, 'surprised', { lookY: -.5 }], [1.8, 'starstruck', { lookY: -.4 }], [6.8, 'thinking', { lookX: -.3, lookY: -.5 }], [9.2, 'idea', { lookY: -.55 }]]);
    clawd(820, 1000, 24, { ...moodE, aR: kf(lt, [[6.6, .1], [7.6, 1.3]], backOut), armR: lensProp(0), tintK: .25, tint: 'blue' });
    camEnd();
  }

  // ============================================================ F: duplicates, busted
  function shotF(t, lt, dur) {
    camBegin(lerp(700, 900, ease(seg(lt, 0, 1.4))), lerp(430, 480, ease(seg(lt, 0, 1.4))), lerp(1.42, 1.18, ease(seg(lt, 0, 1.4))));
    boilSeed('Fbg');
    paint(rectPts(-800, -500, W + 1600, H + 1000), { wash: PAL.night, ink: null });
    boilSeed('Fneb'); paint(ellPts(1400, 700, 520, 300, 22, 10), { fill: PAL.indigo, fillOp: 46, bleed: .3, tex: .5, ink: null });
    for (let i = 0; i < 26; i++) { boilSeed('Fst' + i); const tw = .5 + .5 * Math.sin(lt * (1.5 + hash(i)) + i * 2); paint(starPts(hash(i) * W, hash(i + 50) * 560, 3 + 3 * hash(i + 9) * tw, .4, 4), { wash: PAL.cream, washOp: 120 * tw, ink: null }); }
    for (let i = 0; i < NC; i++) { const hp = hudPos(i); dot(hp[0], hp[1], 10 + 6 * hash(i + 2), FAM[fam(i)], 500 + i, { glowK: .35 }); }

    // two different-word cards fly in and land on (almost) the same point
    const P = [HUD[2][0] + 130, HUD[2][1] - 60];
    const flights = [[[-260, 300], 190, 0, 'fish', 2], [[2180, 210], 220, .25, 'fish', 4]];
    flights.forEach(([from, harc, dt0, doodle, lines], i2) => {
      const p = ease(seg(lt, .3 + dt0, 2.0 + dt0));
      if (p <= 0 || p >= 1) return;
      const [px, py] = arcPt(from, [P[0] + (i2 ? 12 : -12), P[1] + (i2 ? 8 : -6)], harc, p);
      if (p < .62) card(px, py, 108 * (1 - p * .8), (i2 ? -1 : 1) * p * 1.5, 700 + i2, { doodle, lines });
      else dot(px, py, 18 * Math.min(1, (p - .55) * 3.2), FAM[2], 720 + i2);
    });
    const landed = lt > 2.35;
    if (landed) {
      const shy = seg(lt, 6.4, 7.6);
      const look = lt > 4.7 ? (lt > 6.2 ? .9 : -.6) : 0;
      dot(P[0] - 12 + shy * 110, P[1] - 6, 18, FAM[2], 720, { eyes: lt > 4.5, lookX: look, blink: Math.sin(lt * 5) > .93 });
      dot(P[0] + 12, P[1] + 8, 18, FAM[2], 721, { eyes: lt > 4.5, lookX: -look * .8 });
      for (const d of [0, .35]) { const rk = seg(lt, 2.35 + d, 3.35 + d); if (rk > 0 && rk < 1) { boilSeed('Fring' + d); const rr = 30 + 130 * ease(rk); inkLine(ellPts(P[0], P[1], rr, rr * .8, 24).concat([ellPts(P[0], P[1], rr, rr * .8, 24)[0]]), 2.6 * (1 - rk), PAL.cream, 'ink', 1); } }
      const enc = seg(lt, 4.2, 5.0);                     // the lens circles the pair
      if (enc > 0) { boilSeed('Fenc'); const pts = ellPts(P[0], P[1], 92, 74, 30, 3, -.4); inkLine(pts.slice(0, Math.max(2, Math.floor(pts.length * enc))).concat(enc >= 1 ? [pts[0]] : []), 3, PAL.rose, 'dry', .8); }
    }
    // Clawd reacts: take, then the verdict
    const tk = take(lt, 2.6, 1.2);
    const moodF = emotions(lt, [[0, 'thinking', { lookX: .3, lookY: -.2 }], [2.6, 'surprised', { lookX: .5, lookY: -.25 }], [3.9, 'determined', { lookX: .5, lookY: -.2 }], [6.3, 'smug', { lookX: .4 }]]);
    clawd(560, 1000, 26, { ...moodF, dy: moodF.dy + tk.dy, sq: moodF.sq + tk.sq, tintK: .2, tint: 'blue', aR: kf(lt, [[3.9, .2], [4.5, .9]], backOut), armR: lensProp(0) });
    camEnd();
    const bp = seg(lt, 4.35, 4.95), bh = 1 - seg(lt, 7.3, 7.9);
    if (bp > 0 && bh > 0) letter('BUSTED!', 1210, 330, 120, PAL.rose, { pop: backOut(bp) * (1 + .06 * pulse(t, 1)), rot: -.1 + .14 * ease(bp), alpha: 255 * Math.min(1, bp * 3) * bh });
  }

  // ============================================================ G: cluster / outliers / graph
  function shotG(t, lt, dur) {
    const wide = ease(seg(lt, 5.6, 9.4));
    camBegin(lerp(900, 960, wide), lerp(480, 520, wide), lerp(1.18, .92, wide));
    boilSeed('Gbg');
    paint(rectPts(-900, -600, W + 1800, H + 1200), { wash: PAL.night, ink: null });
    boilSeed('Gneb'); paint(ellPts(500, 260, 520, 300, 22, 10), { fill: PAL.violet, fillOp: 36, bleed: .3, tex: .5, ink: null });
    for (let i = 0; i < 30; i++) { boilSeed('Gst' + i); const tw = .5 + .5 * Math.sin(lt * (1.5 + hash(i)) + i * 2); paint(starPts(hash(i) * W, hash(i + 50) * 700, 3 + 3 * hash(i + 9) * tw, .4, 4), { wash: PAL.cream, washOp: 110 * tw, ink: null }); }

    // the neighbor graph draws itself, one family at a time, on the beat
    for (let f = 0; f < 3; f++) {
      const members = []; for (let i = 0; i < NC; i++) if (fam(i) === f) members.push(i);
      for (let a = 0; a < members.length; a++) for (let b = a + 1; b < members.length; b++) {
        if (b !== a + 1 && hash(members[a] * 31 + members[b]) > .6) continue;   // chain edges always, extras by chance
        const k = seg(lt, .3 + f * 1.05 + (a + b) * .16, 1.1 + f * 1.05 + (a + b) * .16);
        if (k <= 0) continue;
        const A = hudPos(members[a]), B = hudPos(members[b]);
        boilSeed('Ge' + members[a] + '_' + members[b]);
        const ex = lerp(A[0], B[0], ease(k)), ey = lerp(A[1], B[1], ease(k));
        inkLine([[A[0], A[1]], [(A[0] + ex) / 2 + jit(2), (A[1] + ey) / 2 - 6], [ex, ey]], 2, mixCol(FAM[f], PAL.cream, .6), 'ink', .4);
      }
    }
    for (let i = 0; i < NC; i++) { const hp = hudPos(i); dot(hp[0], hp[1], (10 + 6 * hash(i + 2)) * (1 + .5 * pulse(t, 1.6) * (wide > .5 ? 1 : 0) * (i % 4 === 0 ? 1 : 0)), FAM[fam(i)], 500 + i, { glowK: .4 }); }

    // the outlier: far away, blinking, flagged
    const ob = .4 + .6 * Math.abs(Math.sin(lt * 2.6));
    glow(OUTLIER[0], OUTLIER[1], 90 * ob, PAL.violet, .5);
    dot(OUTLIER[0], OUTLIER[1], 11, PAL.violet, 900, { eyes: lt > 2.5, lookX: .8, blink: Math.sin(lt * 3.4) > .88 });
    flag(OUTLIER[0] + 52, OUTLIER[1] + 14, 84, seg(lt, 4.3, 5.7));

    // Clawd: walks to the outlier, plants, then holds proud in the wide
    const stx = kf(lt, [[2.4, 700], [4.2, 420]], ease);
    const moodG = emotions(lt, [[0, 'happy', { lookY: -.3 }], [2.2, 'thinking', { lookX: -.7, lookY: .3 }], [4.4, 'determined', { lookX: -.5 }], [5.9, 'proud'], [8.7, 'starstruck', { lookY: -.4 }]]);
    boilSeed('Ghill');
    paint(ellPts(760, 1230, 980, 340, 26, 6), { wash: mixCol(PAL.indigo, PAL.night, .5), ink: PAL.ink, sw: 1 });
    clawd(stx, 1020, lerp(24, 17, wide), { ...moodG, view: lt > 2.4 && lt < 4.2 ? 'q' : 'front', flip: lt > 2.4 && lt < 4.2, walk: lt > 2.4 && lt < 4.2 ? lt * 9 : 0, tintK: .18, tint: 'blue', aL: kf(lt, [[4.3, -.2], [4.9, 1.1], [5.9, .2]], ease) });
    camEnd();
  }

  // ============================================================ H: the sandbox
  function shotH(t, lt, dur) {
    const zi = ease(seg(lt, 3.0, 4.0)) - ease(seg(lt, 7.3, 8.1));   // camera push for the phone gag
    camBegin(lerp(960, 1210, zi), lerp(560 - 10 * Math.sin(lt * .3), 700, zi), lerp(1.04 + .012 * Math.sin(lt * .4), 1.55, zi));
    sandbox(lt, 0);
    starfish(600, 826, 40);
    for (let i = 0; i < 6; i++) { const fk = seg(lt, .1 + i * .12, 1.4 + i * .12); if (fk > 0 && fk < 1) dot(500 + hash(i) * 900, lerp(-60, 700, ease(fk)), 9, FAM[i % 3], 940 + i, {}); }
    pail(1420, 840, 90, seg(lt, 1.2, 10), lt);

    const digK = (lt < 3.05 || lt > 8.8) ? 1 : 0;
    const digPh = bpOf(t) < .5 ? easeOut(bpOf(t) * 2) : 1 - ease((bpOf(t) - .5) * 2);
    for (let i = 0; i < 3; i++) {
      const barP = frac(t / (BEAT * 4) + i * .33);
      if (digK && barP < .5) { const [sx2, sy2] = arcPt([1080, 800], [1400, 760], 120 + 24 * i, barP * 2); paint(ellPts(sx2, sy2, 6 - i, 6 - i, 8), { wash: i === 1 ? FAM[(lt | 0) % 3] : SAND, ink: i === 1 ? PAL.ink : null, sw: .5 }); }
    }
    const moodH = emotions(lt, [[0, 'happy', { lookX: .4, lookY: .3 }], [3.15, 'surprised', { lookX: .85, lookY: .2 }], [4.4, 'confused', { lookX: .5 }], [6.0, 'cool', { lookX: .6 }], [8.7, 'happy', { lookX: .4, lookY: .3 }], [10.5, 'love', { lookX: .2 }]]);
    const patT = seg(lt, 4.5, 5.9), pat = patT > 0 && patT < 1 ? Math.sin(lt * 16) : 0;
    clawd(1000, 900, 25, { ...moodH, rot: digK ? -.06 + .1 * digPh : 0, sq: digK ? .06 * digPh : 0,
      aR: digK ? (.55 - .75 * digPh) : (patT > 0 && patT < 1 ? -.9 + .2 * pat : kf(lt, [[6.0, -.6], [6.5, 1.1], [7.1, 1.1], [7.6, .3]], ease)),
      aL: patT > 0 && patT < 1 ? -.9 - .2 * pat : -.35,
      armR: digK ? ((u, sw) => { inkLine([[0, 0], [u * 1.1, 0]], Math.max(1.6, u * .3), WOODD); paint([[u * 1.1, -u * .5], [u * 1.9, -u * .6], [u * 1.9, u * .6], [u * 1.1, u * .5]], { wash: mixCol(PAL.teal, PAL.ink, .2), ink: PAL.ink, sw: 1 }); }) : undefined });
    sandboxFrame();

    // the phone: hops in close, rings, droops, poofs
    const pin = seg(lt, 3.1, 4.3), pgone = seg(lt, 6.9, 7.35);
    if (pin > 0 && pgone < 1) {
      const px = kf(lt, [[3.1, 1900], [4.3, 1500]], ease);
      const hop2 = Math.abs(Math.sin(pin * Math.PI * 2)) * 70 * (pin < 1 ? 1 : 0);
      push(); if (pgone > 0) { translate(1500, 795); scale(1 - pgone); translate(-1500, -795); }
      phone(px, 795 - hop2, 100, { ring: lt > 3.25 && lt < 5.6 ? 1 : 0, droop: seg(lt, 6.3, 6.9) });
      if (lt > 3.4 && lt < 5.6) emote('music', 1462, 652, 19, .6 + .4 * Math.sin(lt * 7), lt);
      pop();
    }
    poof(1500, 780, 85, pgone);
    // wifi arcs, then the big NO over them (after the camera settles back)
    const wk = seg(lt, 8.2, 9.0), xk = seg(lt, 9.0, 9.8);
    if (wk > 0) { boilSeed('wifi');
      for (let i = 0; i < 3; i++) { const k = clamp(wk * 3 - i), r = 60 + i * 46; if (k > 0) { const pts = ellPts(430, 330, r, r * .9, 20).filter((p2, j) => j >= 11 && j <= 11 + Math.floor(8 * k)); if (pts.length > 1) inkLine(pts, 4 - i * .6, mixCol(PAL.sky, PAL.ink, .25), 'ink', .8); } }
      paint(ellPts(430, 342, 8, 8, 8), { wash: mixCol(PAL.sky, PAL.ink, .25), ink: null });
    }
    if (xk > 0) { boilSeed('wifix'); const c = mixCol(PAL.rose, PAL.ink, .25);
      const e1 = Math.min(1, xk * 2), e2 = (xk - .5) * 2;
      inkLine([[320, 180], [lerp(320, 545, e1 * .5) + jit(3), lerp(180, 380, e1 * .5)], [lerp(320, 545, e1), lerp(180, 380, e1)]], 9, c, 'ink', .3);
      if (xk > .5) inkLine([[545, 180], [lerp(545, 320, e2 * .5) + jit(3), lerp(180, 380, e2 * .5)], [lerp(545, 320, e2), lerp(180, 380, e2)]], 9, c, 'ink', .3); }
    camEnd();
    const op = seg(lt, 9.4, 10.1), oh = 1 - seg(lt, 11.4, 12);
    if (op > 0 && oh > 0) letter('100% OFFLINE', 1150, 250, 90, PAL.teal, { pop: backOut(op), rot: -.05 + .07 * op, alpha: 255 * Math.min(1, op * 3) * oh });
    if (lt < .5) { boilSeed('Hwip'); brushWipe(.5 + lt / 1, [PAL.indigo, SAND]); }
    if (lt > dur - .5) brushWipe((lt - (dur - .5)) / 1, [SAND, PAL.indigo]);
  }

  // ============================================================ I: outro, the ordered sky
  function shotI(t, lt, dur) {
    camBegin(960, 540 + 40 * (1 - ease(seg(lt, 0, 1.6))), 1.02);
    sandbox(lt, .8);
    // the constellation: the opening's chaos, now in gentle order (the rhyme)
    for (let i = 0; i < NC; i++) {
      boilSeed('Icst' + i);
      const a = i / NC * Math.PI, x = 300 + (i / (NC - 1)) * 1320 + 40 * Math.sin(i * 2.2);
      const y = 210 + 130 * Math.sin(a) * (i % 2 ? -1 : 1) * .4 + 60 * hash(i);
      const tw = .6 + .4 * Math.sin(lt * (1.2 + hash(i)) + i);
      glow(x, y, 60 * tw, FAM[fam(i)], .5);
      dot(x, y, 8 + 4 * hash(i + 2), FAM[fam(i)], 960 + i, {});
      if (i > 0 && hash(i * 17) < .6) { const px2 = 300 + ((i - 1) / (NC - 1)) * 1320 + 40 * Math.sin((i - 1) * 2.2), py2 = 210 + 130 * Math.sin((i - 1) / NC * Math.PI) * ((i - 1) % 2 ? -1 : 1) * .4 + 60 * hash(i - 1); inkLine([[px2, py2], [(px2 + x) / 2, (py2 + y) / 2 - 8], [x, y]], .9, mixCol(PAL.cream, PAL.indigo, .35), 'inkfine', .4); }
    }
    starfish(600, 826, 40);
    pail(1420, 840, 90, 1, lt);
    const moodI = emotions(lt, [[0, 'love', { lookY: -.5 }], [2.2, 'happy'], [5.2, 'happy', { eyes: ['wink', 'happy'] }]]);
    const waveK = lt > 2.4 && lt < 5.4 ? Math.sin((lt - 2.4) * 6) : 0;
    clawd(1000, 900, 25, { ...moodI, aR: lt > 2.2 ? 1.1 + .35 * waveK : .3, armR: lt < 2.2 ? lensProp(1) : undefined });
    sandboxFrame();
    camEnd();
    const tp = seg(lt, 2.6, 3.5), cp = seg(lt, 3.4, 4.2), fade = 1 - seg(lt, 5.4, 6.1);
    if (tp > 0 && fade > 0) letter('smol-sim-search', 960, 380, 96, PAL.cream, { pop: backOut(tp), rot: -.02, alpha: 235 * Math.min(1, tp * 2.5) * fade });
    if (cp > 0 && fade > 0) letter('clone it', 960, 480, 52, mixCol(PAL.cream, PAL.teal, .4), { pop: ease(cp), alpha: 220 * cp * fade });
    flushLetters();
    if (lt < .5) brushWipe(.5 + lt / 1, [SAND, PAL.indigo]);
    const ir = seg(lt, 5.9, 7.15);
    if (ir > 0) iris(1000, 800, lerp(1700, 0, ease(ir)), PAL.night);
  }

  shots([[0, shotA], [14.15, shotB], [25.1, shotC], [38.4, shotD], [49.65, shotE], [61.85, shotF], [69.75, shotG], [80.9, shotH], [92.9, shotI]]);
})();
