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

  // Helper: a big animated word callout with pop + slight rotate + beat pulse.
  function call(txt, x, y, size, col, lt, t0, t1, o = {}) {
    const pin = seg(lt, t0, t0 + .5), out = t1 ? seg(lt, t1 - .3, t1) : 0;
    if (pin <= 0 || out >= 1) return;
    const k = backOut(pin) * (1 + .05 * pulse(t, o.beat || 1));
    letter(txt, x, y, size, col, { pop: k, rot: (o.rot ?? -.03) + .05 * (1 - pin), alpha: 255 * Math.min(1, pin * 3) * (1 - out) });
  }
  // Helper: a stamped verdict (slams in with overshoot + shake)
  function stamp(txt, x, y, size, col, lt, t0, t1) {
    const pin = seg(lt, t0, t0 + .28), out = t1 ? seg(lt, t1 - .25, t1) : 0;
    if (pin <= 0 || out >= 1) return;
    letter(txt, x, y, size, col, { pop: backOut(pin), rot: -.12 + .16 * ease(pin), alpha: 255 * Math.min(1, pin * 4) * (1 - out) });
  }

  // ============================================================ A: the grep problem (0–6.56)
  function shotA(t, lt, dur) {
    camBegin(960 + 12 * Math.sin(lt * .4), 540, 1 + .015 * lt);
    boilSeed('Abg');
    paint(rectPts(-600, -400, W + 1200, H + 800), { wash: COOL, ink: null });
    paint(ellPts(900, 1120, 1500, 420, 30, 6), { fill: mixCol(COOL, PAL.indigo, .3), fillOp: 60, bleed: .2, tex: .5, ink: null });
    for (let i = 0; i < 7; i++) {
      const x = 200 + hash(i) * 1520 + 26 * Math.sin(lt * .3 + i * 1.7), y = 150 + hash(i + 40) * 380 + 16 * Math.sin(lt * .42 + i);
      card(x, y, 96 + 36 * hash(i + 80), .12 * Math.sin(i * 9 + lt * .2), i, { lines: 3 });
    }
    // the synonym drifts by BEHIND Clawd — the joke: Clawd never sees the match
    const sx = kf(lt, [[2.4, [2120, 815]], [5.2, [620, 830]], [6.56, [360, 840]]], ease);
    card(sx[0], sx[1], 120, -.08, 111, { doodle: 'fish', lines: 2 });
    const mood = emotions(lt, [[0, 'bored'], [1.4, 'thinking', { lookX: -.6, lookY: -.3 }], [3.0, 'suspicious', { lookX: -.4 }], [5.2, 'confused']]);
    clawd(1150, 900, 26, { ...mood, aR: kf(lt, [[0, .2], [1.2, .95], [5.4, .95], [6.2, .3]], ease), armR: lensProp(0), aL: -.4, flip: true });
    card(1352, 668 + mood.dy * 3 + 7 * Math.sin(lt * 1.7), 84, .1, 120, { doodle: 'fish', lines: 2 });
    camEnd();
    // text: point out the missed match
    call('grep: exact words only', 960, 175, 58, mixCol(PAL.ink, PAL.cream, .2), lt, .6, 3.2, { rot: -.02 });
    if (lt > 4.4 && lt < 6.2) { const k = seg(lt, 4.4, 4.8); letter('...right there', 470, 720, 46, PAL.rose, { pop: backOut(k), rot: .06, alpha: 255 * k * (1 - seg(lt, 5.8, 6.2)) }); }
    if (lt < .4) iris(1150, 800, lerp(0, 1600, easeIn(lt / .4)), PAL.paper);
    if (lt > dur - .3) brushWipe((lt - (dur - .3)) / .6, [PAL.clay, PAL.rose]);
  }

  // ============================================================ B: meet (6.56–11.96)
  function shotB(t, lt, dur) {
    camBegin(960, 540 - 8 * Math.sin(lt * .5), 1.02);
    boilSeed('Bbg');
    paint(rectPts(-600, -400, W + 1200, H + 800), { wash: WARM, ink: null });
    paint(ellPts(960, 300, 900, 420, 26, 8), { fill: PAL.rose, fillOp: 42, bleed: .25, tex: .5, ink: null });
    for (let i = 0; i < 10; i++) { boilSeed('spk' + i); const k = frac(lt * .16 + hash(i)); paint(ellPts(120 + hash(i) * 1700, 1100 - k * 900, 6, 6, 8), { wash: FAM[i % 3], washOp: 170 * Math.sin(k * Math.PI), ink: null }); }
    const hop = jump(lt, .5, 1.2, 6);
    const mood = emotions(lt, [[0, 'surprised'], [.8, 'excited'], [2.6, 'proud', { emote: 'bulb' }], [4.2, 'happy']]);
    clawd(960, 940, 30, { ...mood, dy: mood.dy + hop.dy, sq: mood.sq + hop.sq, aR: kf(lt, [[2.4, .3], [3.0, 1.25]], backOut), armR: lensProp(seg(lt, 3.1, 4.4)) });
    camEnd();
    call('smol-sim-search', 960, 250, 104, PAL.clay, lt, .3, 0, { beat: 1 });
    call('tiny crab.', 620, 700, 62, PAL.teal, lt, 2.6, 0, { rot: -.05 });
    call('BIG BRAIN.', 1330, 760, 68, PAL.ochre, lt, 3.3, 0, { rot: .05 });
    if (lt < .3) brushWipe(.5 + lt / .6, [PAL.clay, PAL.rose]);
    if (lt > dur - .3) brushWipe((lt - (dur - .3)) / .6, [PAL.teal, PAL.indigo]);
  }

  // ============================================================ C: search by meaning (11.96–20.10)
  function shotC(t, lt, dur) {
    camBegin(960, 540, 1.02 + .01 * Math.sin(lt * .5));
    boilSeed('Cbg');
    paint(rectPts(-600, -400, W + 1200, H + 800), { wash: mixCol(PAL.indigo, PAL.cream, .74), ink: null });
    paint(ellPts(960, 900, 1200, 380, 26, 8), { fill: PAL.teal, fillOp: 30, bleed: .2, tex: .5, ink: null });
    call('search by MEANING', 960, 150, 74, PAL.teal, lt, .3, 0, { rot: -.02 });
    // two phrase-cards fly in, become dots meeting at the centre
    const P = [960, 640];
    const flights = [[[-320, 560], -220, 0, 5], [[2240, 560], -240, .2, 5]];
    flights.forEach(([from, harc, dt0, lines], i2) => {
      const p = ease(seg(lt, 1.4 + dt0, 3.2 + dt0));
      if (p <= 0 || p >= 1) return;
      const [px, py] = arcPt(from, [P[0] + (i2 ? 30 : -30), P[1]], harc, p);
      if (p < .64) card(px, py, 118 * (1 - p * .55), (i2 ? -1 : 1) * (1 - p) * .6, 700 + i2, { doodle: 'fish', lines });
      else dot(px, py, 22 * Math.min(1, (p - .58) * 3), FAM[1], 720 + i2, { glowK: .5 });
    });
    if (lt > 3.0) { const rk = seg(lt, 3.0, 3.9); if (rk < 1) { boilSeed('Cring'); const rr = 40 + 150 * ease(rk); inkLine(ellPts(P[0], P[1], rr, rr * .8, 26).concat([ellPts(P[0], P[1], rr, rr * .8, 26)[0]]), 3 * (1 - rk), PAL.teal, 'ink', 1); } if (lt > 3.2) { dot(P[0] - 26, P[1], 22, FAM[1], 720, { glowK: .5 }); dot(P[0] + 26, P[1], 22, FAM[1], 721, { glowK: .5 }); glow(P[0], P[1], 200, PAL.teal, .4); } }
    // the two phrases as text, sliding to an equals
    const s1 = ease(seg(lt, 3.6, 4.6)), s2 = ease(seg(lt, 4.9, 6.4));
    if (s1 > 0) { letter('"charged twice"', lerp(430, 620, s1), 880, 52, PAL.clay, { pop: 1, alpha: 255 * Math.min(1, s1 * 3) * (1 - seg(lt, 7.4, 7.9)) });
                  letter('"billed double"', lerp(1490, 1300, s1), 880, 52, PAL.ochre, { pop: 1, alpha: 255 * Math.min(1, s1 * 3) * (1 - seg(lt, 7.4, 7.9)) }); }
    if (s2 > 0) letter('=', 960, 880, 70 * backOut(s2), PAL.teal, { pop: 1, alpha: 255 * s2 * (1 - seg(lt, 7.4, 7.9)) });
    call('same idea. no magic words.', 960, 1010, 46, mixCol(PAL.ink, PAL.cream, .15), lt, 6.4, 0, { rot: 0 });
    const mood = emotions(lt, [[0, 'thinking', { lookY: -.3 }], [3.2, 'happy', { lookY: -.2 }], [6.2, 'proud']]);
    clawd(300, 1000, 22, mood);
    camEnd();
    if (lt > dur - .3) brushWipe((lt - (dur - .3)) / .6, [PAL.indigo, PAL.night]);
  }

  // ============================================================ D: analytics montage (20.10–25.93)
  function shotD(t, lt, dur) {
    camBegin(960, 540, 1.03);
    boilSeed('Dbg');
    paint(rectPts(-600, -400, W + 1200, H + 800), { wash: PAL.night, ink: null });
    for (let i = 0; i < 26; i++) { boilSeed('Dst' + i); const tw = .5 + .5 * Math.sin(lt * (1.5 + hash(i)) + i * 2); paint(starPts(hash(i) * W, hash(i + 50) * 640, 3 + 3 * hash(i + 9) * tw, .4, 4), { wash: PAL.cream, washOp: 110 * tw, ink: null }); }
    // three sub-beats
    const sub = lt < 1.95 ? 0 : lt < 3.9 ? 1 : 2;
    if (sub === 0) {                       // duplicates busted
      const P = [720, 560];
      for (const d of [-1, 1]) dot(P[0] + d * 30, P[1], 26, FAM[0], 300 + d, { glowK: .5 });
      const enc = seg(lt, .3, 1.0); if (enc < 1) { boilSeed('Denc'); const pts = ellPts(P[0], P[1], 120, 96, 30, 3); inkLine(pts.slice(0, Math.max(2, Math.floor(pts.length * enc))).concat(enc >= 1 ? [pts[0]] : []), 4, PAL.rose, 'ink', .8); }
      call('duplicates?', 720, 330, 60, PAL.cream, lt, .1, 1.9, { rot: -.03 });
      stamp('BUSTED', 1280, 620, 128, PAL.rose, lt, 1.0, 1.95);
    } else if (sub === 1) {                // themes sorted
      for (let i = 0; i < 9; i++) { const f = i % 3, c = [[540, 500], [960, 460], [1360, 560]][f]; const a = hash(i * 5) * TAU, r = 70 * ease(seg(lt, 2.0, 2.9)); dot(c[0] + Math.cos(a) * r, c[1] + Math.sin(a) * r * .8, 22, FAM[f], 320 + i, { glowK: .4 }); }
      call('themes?', 720, 320, 60, PAL.cream, lt, 2.0, 3.9, { rot: -.03 });
      stamp('SORTED', 1150, 780, 120, PAL.teal, lt, 2.95, 3.9);
    } else {                                // outliers flagged
      for (let i = 0; i < 8; i++) { const a = hash(i) * TAU; dot(920 + Math.cos(a) * 150, 560 + Math.sin(a) * 110, 20, FAM[i % 3], 340 + i, { glowK: .35 }); }
      const ob = .5 + .5 * Math.abs(Math.sin(lt * 6));
      glow(360, 720, 90 * ob, PAL.violet, .5); dot(360, 720, 22, PAL.violet, 360, { eyes: true, lookX: .6 });
      flag(410, 734, 90, seg(lt, 4.2, 5.2));
      call('weird stuff?', 1180, 330, 60, PAL.cream, lt, 3.95, 5.83, { rot: .03 });
      stamp('FLAGGED', 640, 900, 116, PAL.violet, lt, 4.9, 5.83);
    }
    camEnd();
    if (lt > dur - .3) brushWipe((lt - (dur - .3)) / .6, [PAL.night, mixCol(PAL.cream, PAL.ochre, .16)]);
  }

  // ============================================================ E: install (25.93–33.40)
  function shotE(t, lt, dur) {
    camBegin(960, 560, 1.03 + .01 * Math.sin(lt * .45));
    boilSeed('Ebg');
    paint(rectPts(-600, -400, W + 1200, H + 800), { wash: mixCol(PAL.cream, PAL.ochre, .16), ink: null });
    paint(rectPts(-600, 902, W + 1200, 600), { wash: mixCol(PAL.sap, PAL.cream, .5), ink: null });
    inkLine([[300, 905], [960, 907], [1620, 905]], 1.4, mixCol(PAL.ink, PAL.cream, .3), 'ink', .4);
    crate(560, 900, 260, 'E1');
    const ck = seg(lt, .5, 1.6);
    if (ck > 0) { const nx = lerp(560, 940, backOut(ck)); crate(nx, 900 - 55 * Math.sin(Math.PI * Math.min(1, ck)), 260, 'E2', { lid: kf(lt, [[3.2, 0], [4.0, 1]], backOut) }); poof(750, 880, 55, seg(lt, .6, 1.3)); }
    // parts arc out on "batteries"
    const parts = [[1230, 'gear', PAL.teal], [1410, 'bat', PAL.sap], [1520, 'bat', PAL.sap]];
    parts.forEach(([tx, kind, col], i) => {
      const p = seg(lt, 4.0 + i * .22, 4.9 + i * .22); if (p <= 0) return;
      const [px, py] = arcPt([940, 740], [tx, 856], 200 + 26 * i, ease(p));
      const w2 = spring(lt, 4.9 + i * .22, .12, 9), bop = kind === 'bat' ? Math.abs(7 * pulse(t, 2)) * seg(lt, 5.6, 6.2) : 0;
      boilSeed('part' + i); push(); translate(px, py - bop); rotate(p < 1 ? p * 2.5 : w2 * .35);
      if (kind === 'gear') { for (let k2 = 0; k2 < 8; k2++) { const a = k2 / 8 * TAU; paint(rectPts(Math.cos(a) * 46 - 8, Math.sin(a) * 46 - 8, 16, 16, .5), { wash: col, ink: PAL.ink, sw: 1 }); } paint(ellPts(0, 0, 43, 43, 16), { wash: col, ink: PAL.ink, sw: 1.4 }); paint(ellPts(0, 0, 13, 13, 10), { wash: PAL.cream, ink: PAL.ink, sw: 1 }); }
      else { paint(rrPts(-18, -46, 36, 84, 7, 1), { wash: col, ink: PAL.ink, sw: 1.4 }); paint(rrPts(-8, -56, 16, 11, 3, .5), { wash: PAL.ink, ink: null }); inkLine([[-8, -11], [8, -11]], 3, PAL.cream); inkLine([[0, -19], [0, -3]], 3, PAL.cream); }
      pop();
    });
    // the download cloud, shooed
    const ckin = seg(lt, 2.0, 2.7), cko = seg(lt, 3.3, 3.7);
    cloud(kf(lt, [[2.0, 2150], [2.7, 1560], [3.3, 1560], [3.7, 1980]], ease), 300, 92, (1 - cko) * Math.min(1, ckin * 3), lt);
    poof(1900, 320, 85, seg(lt, 3.65, 4.2));
    const mood = emotions(lt, [[0, 'happy', { lookX: -.4 }], [.6, 'mischief'], [2.0, 'suspicious', { lookX: .8, lookY: -.5 }], [3.3, 'angry', { lookX: .85, lookY: -.5 }], [3.9, 'proud', { lookX: .5 }], [5.6, 'happy']]);
    const shooA = lt > 3.3 && lt < 3.8 ? .9 + .55 * Math.sin(lt * 13) : .3;
    clawd(kf(lt, [[0, 780], [.5, 1180], [2.0, 1180], [2.6, 1330], [12, 1330]], ease), 902, 23, { ...mood, aR: shooA, aL: -.3 });
    camEnd();
    call('one clone.', 470, 260, 58, PAL.clay, lt, .5, 2.0, { rot: -.04 });
    call('one script.', 470, 340, 58, PAL.clay, lt, 1.3, 2.6, { rot: -.02 });
    stamp('ZERO DOWNLOADS', 1180, 250, 78, PAL.teal, lt, 3.7, 5.4);
    call('batteries included', 1300, 1010, 48, PAL.sap, lt, 5.4, 7.4, { rot: .02 });
    if (lt < .12) flash((1 - lt / .12) * .7, PAL.cream);
    if (lt > dur - .3) brushWipe((lt - (dur - .3)) / .6, [mixCol(PAL.cream, PAL.ochre, .16), SAND]);
  }

  // ============================================================ F: sandbox (33.40–40.44)
  function shotF(t, lt, dur) {
    camBegin(960 + 60 * ease(seg(lt, 2.2, 3.0)) - 60 * ease(seg(lt, 4.6, 5.4)), 580, 1.05 + .1 * ease(seg(lt, 2.2, 3.0)) - .1 * ease(seg(lt, 4.6, 5.4)));
    sandbox(lt, 0); starfish(600, 826, 40); pail(1420, 840, 90, 1, lt);
    const digK = (lt < 2.0 || lt > 5.6);
    const digPh = bpOf(t) < .5 ? easeOut(bpOf(t) * 2) : 1 - ease((bpOf(t) - .5) * 2);
    const mood = emotions(lt, [[0, 'happy', { lookX: .4, lookY: .3 }], [2.1, 'surprised', { lookX: .8 }], [3.2, 'confused', { lookX: .3 }], [4.5, 'cool', { lookX: .6 }], [5.8, 'happy', { lookX: .3, lookY: .3 }]]);
    const patT = seg(lt, 3.3, 4.4), pat = patT > 0 && patT < 1 ? Math.sin(lt * 16) : 0;
    clawd(1000, 900, 25, { ...mood, rot: digK ? -.06 + .1 * digPh : 0, sq: digK ? .06 * digPh : 0,
      aR: digK ? (.55 - .75 * digPh) : (patT > 0 && patT < 1 ? -.9 + .2 * pat : kf(lt, [[4.4, -.6], [4.9, 1.1], [5.6, .3]], ease)),
      aL: patT > 0 && patT < 1 ? -.9 - .2 * pat : -.35,
      armR: digK ? ((u, sw) => { inkLine([[0, 0], [u * 1.1, 0]], Math.max(1.6, u * .3), WOODD); paint([[u * 1.1, -u * .5], [u * 1.9, -u * .6], [u * 1.9, u * .6], [u * 1.1, u * .5]], { wash: mixCol(PAL.teal, PAL.ink, .2), ink: PAL.ink, sw: 1 }); }) : undefined });
    sandboxFrame();
    // phone gag
    const pin = seg(lt, 2.1, 3.1), pgone = seg(lt, 4.5, 4.9);
    if (pin > 0 && pgone < 1) { const px = kf(lt, [[2.1, 1900], [3.1, 1520]], ease), hop2 = Math.abs(Math.sin(pin * Math.PI * 2)) * 65 * (pin < 1 ? 1 : 0);
      push(); if (pgone > 0) { translate(1520, 795); scale(1 - pgone); translate(-1520, -795); } phone(px, 795 - hop2, 96, { ring: lt > 2.2 && lt < 4.2 ? 1 : 0, droop: seg(lt, 4.0, 4.5) });
      if (lt > 2.3 && lt < 4.2) emote('music', 1482, 650, 18, .6 + .4 * Math.sin(lt * 7), lt); pop(); }
    poof(1520, 780, 80, pgone);
    camEnd();
    call('never phones home', 960, 200, 62, PAL.cream, lt, .3, 2.0, { rot: -.02 });
    call('...no phone!', 1180, 360, 54, PAL.rose, lt, 3.4, 4.6, { rot: .05 });
    stamp('100% OFFLINE', 960, 250, 92, PAL.teal, lt, 5.0, 7.04);
    if (lt < .3) brushWipe(.5 + lt / .6, [mixCol(PAL.cream, PAL.ochre, .16), SAND]);
    if (lt > dur - .3) brushWipe((lt - (dur - .3)) / .6, [SAND, PAL.indigo]);
  }

  // ============================================================ G: outro (40.44–46.5)
  function shotG(t, lt, dur) {
    camBegin(960, 540 + 30 * (1 - ease(seg(lt, 0, 1.4))), 1.02);
    sandbox(lt, .8);
    for (let i = 0; i < NC; i++) { boilSeed('Gc' + i); const x = 300 + (i / (NC - 1)) * 1320 + 40 * Math.sin(i * 2.2), y = 210 + 130 * Math.sin(i / NC * Math.PI) * (i % 2 ? -1 : 1) * .4 + 60 * hash(i), tw = .6 + .4 * Math.sin(lt * (1.2 + hash(i)) + i); glow(x, y, 60 * tw, FAM[fam(i)], .5); dot(x, y, 8 + 4 * hash(i + 2), FAM[fam(i)], 960 + i, {}); if (i > 0 && hash(i * 17) < .6) { const px2 = 300 + ((i - 1) / (NC - 1)) * 1320 + 40 * Math.sin((i - 1) * 2.2), py2 = 210 + 130 * Math.sin((i - 1) / NC * Math.PI) * ((i - 1) % 2 ? -1 : 1) * .4 + 60 * hash(i - 1); inkLine([[px2, py2], [(px2 + x) / 2, (py2 + y) / 2 - 8], [x, y]], .9, mixCol(PAL.cream, PAL.indigo, .35), 'inkfine', .4); } }
    starfish(600, 826, 40); pail(1420, 840, 90, 1, lt);
    const mood = emotions(lt, [[0, 'love', { lookY: -.4 }], [1.8, 'happy', { eyes: ['wink', 'happy'] }]]);
    const waveK = lt > 1.6 ? Math.sin((lt - 1.6) * 6) : 0;
    clawd(1000, 900, 25, { ...mood, aR: lt > 1.4 ? 1.1 + .35 * waveK : .3, armR: lt < 1.4 ? lensProp(1) : undefined });
    sandboxFrame();
    camEnd();
    const fade = 1 - seg(lt, 5.0, 5.9);
    call('smol-sim-search', 960, 380, 96, PAL.cream, lt, .8, 0, { beat: 1 });
    if (lt > 2.0 && fade > 0) letter('clone it. ask better questions.', 960, 480, 46, mixCol(PAL.cream, PAL.teal, .45), { pop: ease(seg(lt, 2.0, 2.8)), alpha: 220 * seg(lt, 2.0, 2.8) * fade });
    flushLetters();
    if (lt < .3) brushWipe(.5 + lt / .6, [SAND, PAL.indigo]);
    const ir = seg(lt, 5.6, 6.6); if (ir > 0) iris(1000, 800, lerp(1700, 0, ease(ir)), PAL.night);
  }

  shots([[0, shotA], [6.56, shotB], [11.96, shotC], [20.10, shotD], [25.93, shotE], [33.40, shotF], [40.44, shotG]]);
})();
