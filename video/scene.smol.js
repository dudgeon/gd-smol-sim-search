// smol.js — "smol-sim-search", square (1080x1080), ~30s, VO-driven. See STORYBOARD.md.
// Built for small screens: tight framing, big Clawd, big punchy text. Audio: vo/voiceover_music.wav.
(() => {
  const CX = 540, CY = 540;
  const COOL = mixCol(PAL.sky, PAL.paper, .45), WARM = mixCol(PAL.cream, PAL.rose, .25);
  const SAND = '#EFD9A7', WOOD = '#C89B6B', WOODD = '#B3865A', TERM = '#20262E';
  const FAM = [PAL.clay, PAL.teal, PAL.ochre];

  function card(x, y, w, rot, key, o = {}) {
    boilSeed('card' + key); const h = w * 1.28;
    push(); translate(x, y); rotate(rot);
    paint(rrPts(-w / 2, -h / 2, w, h, w * .12, 1.5), { wash: PAL.cream, ink: PAL.ink, sw: Math.max(.7, w * .014) });
    for (let i = 0; i < (o.lines ?? 3); i++) { const ly = -h * .28 + i * h * .2, lw = w * (.62 - .13 * hash(key * 7 + i));
      inkLine([[-w * .32, ly], [-w * .32 + lw * .5, ly + jit(1.5)], [-w * .32 + lw, ly + jit(1.5)]], Math.max(.7, w * .02), mixCol(PAL.ink, PAL.cream, .25), 'inkfine', .5); }
    if (o.doodle === 'fish') { const s = w * .17, fx = w * .18, fy = h * .33;
      paint(ellPts(fx, fy, s, s * .55, 12, .5), { wash: PAL.teal, ink: PAL.ink, sw: .6 });
      paint([[fx - s * .8, fy], [fx - s * 1.5, fy - s * .5], [fx - s * 1.5, fy + s * .5]], { wash: PAL.teal, ink: PAL.ink, sw: .6 });
      paint(ellPts(fx + s * .45, fy - s * .12, s * .09, s * .09, 6), { wash: PAL.ink, ink: null }); }
    pop();
  }
  function dot(x, y, r, col, key, o = {}) {
    boilSeed('dot' + key);
    if (o.glowK) glow(x, y, r * 6, col, .5 * o.glowK);
    paint(ellPts(x, y, r, r, 16, .8), { wash: col, ink: PAL.ink, sw: Math.max(.7, r * .1) });
    if (o.eyes) { const e = r * .3, dx = r * .34, lx = (o.lookX ?? 0) * r * .16;
      for (const s of [-1, 1]) { paint(ellPts(x + s * dx + lx, y - r * .12, e, o.blink ? e * .1 : e * 1.4, 8), { wash: PAL.cream, ink: null });
        if (!o.blink) paint(ellPts(x + s * dx + lx * 1.7, y - r * .12, e * .42, e * .55, 6), { wash: PAL.ink, ink: null }); } }
  }
  function lensProp(dotsK = 0) {
    return (u, sw) => { const r = u * 1.7;
      inkLine([[0, 0], [r * .7, 0]], Math.max(1.4, u * .2), PAL.ink);
      paint(ellPts(r * 1.45, 0, r, r, 22, .6), { wash: '#DDEDF5', washOp: 245, ink: PAL.ink, sw: Math.max(1, u * .12) });
      inkLine([[r * 1.02, -r * .42], [r * 1.34, -r * .6]], Math.max(1, u * .12), PAL.cream, 'ink', .4);
      if (dotsK > 0) { const dd = [[-.28, -.22, FAM[0]], [.3, .02, FAM[1]], [-.04, .34, FAM[2]]];
        for (let i = 0; i < 3; i++) { const [ox, oy, c] = dd[i], k = clamp(dotsK * 3 - i);
          if (k > 0) paint(ellPts(r * 1.45 + ox * r, oy * r, r * .18 * backOut(k), r * .18 * backOut(k), 10), { wash: c, ink: null }); } } };
  }
  function poof(x, y, s, k) { if (k <= 0 || k >= 1) return; boilSeed('poof' + ((x * 7 + y) | 0));
    for (let i = 0; i < 6; i++) { const a = i / 6 * TAU + hash(i) * .8, d = s * (.4 + 1.1 * ease(k));
      paint(ellPts(x + Math.cos(a) * d, y + Math.sin(a) * d * .7, s * .22 * (1 - k), s * .2 * (1 - k), 8, 1), { wash: PAL.cream, washOp: 210 * (1 - k), ink: null }); } }
  function phone(x, y, s, o = {}) { boilSeed('phone');
    push(); translate(x, y); rotate((o.ring ? .09 * Math.sin(T * 40) : 0) + (o.droop || 0) * .35);
    paint(rrPts(-s * .55, -s * .5, s * 1.1, s * .5, s * .12, 1), { wash: PAL.night, ink: PAL.ink, sw: 1.2 });
    paint(ellPts(0, -s * .28, s * .18, s * .18, 10), { wash: PAL.cream, ink: PAL.ink, sw: .8 });
    const hy = -s * .62 + (o.droop || 0) * s * .18;
    paint(rrPts(-s * .62, hy - s * .16, s * 1.24, s * .2, s * .1, 1), { wash: PAL.night, ink: PAL.ink, sw: 1.2 });
    for (const q of [-1, 1]) paint(ellPts(q * s * .55, hy - s * .08, s * .17, s * .2, 10), { wash: PAL.night, ink: PAL.ink, sw: 1.2 }); pop(); }
  function flag(x, y, s, plant) { if (plant <= 0) return; const p = ease(Math.min(1, plant * 1.4)), wob = spring(plant, 1 / 1.4, .12, 9);
    push(); translate(x, lerp(y - 180, y, p)); rotate(wob * .4);
    inkLine([[0, 0], [0, -s]], Math.max(1.6, s * .05), PAL.ink); paint([[0, -s], [s * .62, -s * .8], [0, -s * .6]], { wash: PAL.rose, ink: PAL.ink, sw: 1.2 }); pop(); }
  function starfish(x, y, s) { boilSeed('strf'); paint(starPts(x, y, s, .5, 5, .3), { wash: PAL.ochre, ink: PAL.ink, sw: 1.2 }); }
  function pail(x, y, s) { boilSeed('pail');
    paint([[x - s * .55, y - s], [x + s * .55, y - s], [x + s * .42, y], [x - s * .42, y]], { wash: PAL.teal, ink: PAL.ink, sw: 1.4 });
    paint(ellPts(x, y - s, s * .55, s * .12, 14, 1), { wash: mixCol(PAL.teal, PAL.ink, .25), ink: PAL.ink, sw: 1.2 });
    inkLine(ellPts(x, y - s * .9, s * .58, s * .5, 16).slice(8, 17), Math.max(1.2, s * .05), PAL.ink, 'ink', .8); }
  function sandbox(skyK) { boilSeed('sbsky');
    paint(rectPts(-400, -400, W + 800, H + 800), { wash: mixCol(WARM, PAL.indigo, .6 * skyK), ink: null });
    if (skyK < .5) glow(820, 210, 260, PAL.ochre, .5 * (1 - skyK * 2));
    boilSeed('sbsand'); paint(ellPts(CX, 760, 560, 130, 30, 4), { wash: SAND, fill: mixCol(SAND, PAL.ochre, .5), fillOp: 55, bleed: .12, tex: .5, ink: PAL.ink, sw: 1.2 });
    boilSeed('sbfloor'); paint(rectPts(-400, 840, W + 800, 600), { wash: mixCol(PAL.sap, PAL.cream, .55), ink: null }); }
  function sandboxFrame() { boilSeed('sbf'); paint(rrPts(60, 800, 960, 96, 12, 2), { wash: WOOD, ink: PAL.ink, sw: 1.6 }); paint(rrPts(60, 800, 960, 26, 10, 2), { wash: WOODD, ink: null }); }

  // ---------- PPG-flavoured text ----------
  function boom(txt, x, y, size, txtCol, bgCol, lt, t0, t1, o = {}) {
    const pin = seg(lt, t0, t0 + .32), out = t1 ? seg(lt, t1 - .25, t1) : 0;
    if (pin <= 0 || out >= 1) return;
    const k = backOut(pin), al = Math.min(1, pin * 4) * (1 - out), rot = (o.rot ?? -.06) + .12 * (1 - pin);
    const wob = 1 + .04 * pulse(T, o.beat || 1);
    if (bgCol) { boilSeed('boombg' + txt); push(); translate(x, y); rotate(rot); scale(k * wob);
      const rw = size * txt.length * .34 + size * .6, rh = size * 1.3;
      if (o.burst) { const pts = [], n = 16; for (let i = 0; i < n; i++) { const a = i / n * TAU, rr = (i % 2 ? .72 : 1); pts.push([Math.cos(a) * rw * .6 * rr, Math.sin(a) * rh * .8 * rr]); } paint(pts, { wash: bgCol, ink: PAL.ink, sw: 3 }); }
      else paint(rrPts(-rw / 2, -rh / 2, rw, rh, rh * .28, 2), { wash: bgCol, ink: PAL.ink, sw: 3 });
      pop(); }
    letter(txt, x, y, size * wob, txtCol, { pop: bgCol ? 1 : k, rot, alpha: 255 * al });
  }
  function call(txt, x, y, size, col, lt, t0, t1, o = {}) {
    const pin = seg(lt, t0, t0 + .4), out = t1 ? seg(lt, t1 - .3, t1) : 0;
    if (pin <= 0 || out >= 1) return;
    letter(txt, x, y, size, col, { pop: backOut(pin), rot: (o.rot ?? -.02) + .05 * (1 - pin), alpha: 255 * Math.min(1, pin * 3) * (1 - out) });
  }
  function cmd(txt, x, y, size, lt, t0, t1) {
    const pin = seg(lt, t0, t0 + .3), out = t1 ? seg(lt, t1 - .25, t1) : 0;
    if (pin <= 0 || out >= 1) return;
    const k = backOut(pin), al = Math.min(1, pin * 4) * (1 - out);
    boilSeed('cmdbg' + txt); push(); translate(x, y); scale(k);
    const w = size * txt.length * .62 + size * 1.2;
    paint(rrPts(-w / 2, -size * .85, w, size * 1.7, size * .35, 1.5), { wash: TERM, ink: PAL.ink, sw: 2.5 });
    for (let i = 0; i < 3; i++) paint(ellPts(-w / 2 + size * (.55 + i * .34), -size * .42, size * .11, size * .11, 8), { wash: [PAL.rose, PAL.ochre, PAL.sap][i], ink: null });
    pop();
    letter(txt, x + size * .55, y + size * .14, size, mixCol(PAL.cream, PAL.teal, .25), { pop: 1, alpha: 255 * al });
  }

  // ============================================================ A: keyword miss (0–3.97)
  function shotA(t, lt, dur) {
    camBegin(CX + 8 * Math.sin(lt * .5), CY + 40, 1.15);
    boilSeed('Abg'); paint(rectPts(-400, -400, W + 800, H + 800), { wash: COOL, ink: null });
    const sx = kf(lt, [[.6, [1180, 560]], [3.4, [120, 600]]], ease);
    card(sx[0], sx[1], 150, -.08, 111, { doodle: 'fish', lines: 2 });
    const mood = emotions(lt, [[0, 'thinking', { lookX: -.5, lookY: -.2 }], [1.6, 'suspicious', { lookX: -.4 }], [2.8, 'confused']]);
    clawd(560, 900, 42, { ...mood, aR: kf(lt, [[0, .5], [.7, 1.0]], ease), armR: lensProp(0), aL: -.4, flip: true });
    card(760, 560 + mood.dy * 4 + 8 * Math.sin(lt * 1.7), 120, .1, 120, { doodle: 'fish', lines: 2 });
    camEnd();
    boom('KEYWORD', CX, 220, 110, PAL.cream, PAL.clay, lt, .3, 0, { rot: -.05, burst: true });
    call('finds only exact words', CX, 350, 46, PAL.ink, lt, 1.1, 0, { rot: .01 });
    if (lt < .3) iris(560, 700, lerp(0, 1400, easeIn(lt / .3)), PAL.paper);
    if (lt > dur - .28) brushWipe((lt - (dur - .28)) / .56, [PAL.clay, PAL.rose]);
  }

  // ============================================================ B: meet (3.97–8.32)
  function shotB(t, lt, dur) {
    camBegin(CX, CY - 10, 1.04);
    boilSeed('Bbg'); paint(rectPts(-400, -400, W + 800, H + 800), { wash: WARM, ink: null });
    paint(ellPts(CX, 280, 700, 360, 26, 8), { fill: PAL.rose, fillOp: 42, bleed: .25, tex: .5, ink: null });
    for (let i = 0; i < 10; i++) { boilSeed('spk' + i); const k = frac(lt * .2 + hash(i)); paint(ellPts(80 + hash(i) * 920, 1000 - k * 820, 7, 7, 8), { wash: FAM[i % 3], washOp: 180 * Math.sin(k * Math.PI), ink: null }); }
    const hop = jump(lt, .4, 1.1, 7);
    const mood = emotions(lt, [[0, 'surprised'], [.7, 'excited'], [2.4, 'proud', { emote: 'bulb' }], [3.6, 'happy']]);
    clawd(CX, 940, 48, { ...mood, dy: mood.dy + hop.dy, sq: mood.sq + hop.sq, aR: kf(lt, [[2.2, .3], [2.8, 1.2]], backOut), armR: lensProp(seg(lt, 2.9, 4.0)) });
    camEnd();
    boom('smol-sim-search', CX, 250, 66, PAL.cream, PAL.clay, lt, .3, 0, { rot: -.03, beat: 1 });
    call('tiny crab.', 300, 640, 58, PAL.teal, lt, 2.3, 0, { rot: -.06 });
    call('BIG BRAIN.', 800, 700, 64, PAL.ochre, lt, 3.0, 0, { rot: .06 });
    if (lt < .28) brushWipe(.5 + lt / .56, [PAL.clay, PAL.rose]);
    if (lt > dur - .28) brushWipe((lt - (dur - .28)) / .56, [PAL.teal, TERM]);
  }

  // ============================================================ C: install, honest (8.32–12.55)
  function shotC(t, lt, dur) {
    camBegin(CX, CY, 1.03);
    boilSeed('Cbg'); paint(rectPts(-400, -400, W + 800, H + 800), { wash: mixCol(TERM, PAL.indigo, .3), ink: null });
    boilSeed('term'); paint(rrPts(140, 300, 800, 470, 22, 2), { wash: TERM, ink: PAL.ink, sw: 2.5 });
    paint(rrPts(140, 300, 800, 60, 22, 2), { wash: mixCol(TERM, PAL.cream, .12), ink: null });
    for (let i = 0; i < 3; i++) paint(ellPts(185 + i * 40, 330, 11, 11, 8), { wash: [PAL.rose, PAL.ochre, PAL.sap][i], ink: null });
    clawd(320, 770, 30, { ...emotions(lt, [[0, 'determined', { lookX: .3 }], [2.2, 'happy', { lookX: .2 }], [3.2, 'proud']]), noShadow: true });
    camEnd();
    cmd('git clone …', CX + 60, 430, 38, lt, .5, 0);
    cmd('./setup.sh', CX + 60, 560, 42, lt, 1.9, 0);
    call('run once', 830, 560, 40, PAL.teal, lt, 2.6, 0, { rot: .04 });
    call('one download — then fully offline', CX, 910, 40, PAL.cream, lt, 3.0, 0, { rot: 0 });
    if (lt < .28) brushWipe(.5 + lt / .56, [PAL.teal, TERM]);
    if (lt > dur - .28) brushWipe((lt - (dur - .28)) / .56, [TERM, mixCol(PAL.indigo, PAL.cream, .7)]);
  }

  // ============================================================ D: the skill workflow (12.55–19.94)
  function shotD(t, lt, dur) {
    camBegin(CX, CY, 1.02);
    boilSeed('Dbg'); paint(rectPts(-400, -400, W + 800, H + 800), { wash: mixCol(PAL.indigo, PAL.cream, .74), ink: null });
    const folderK = seg(lt, 1.6, 2.4), fk = backOut(Math.min(1, folderK * 1.5));
    if (fk > .02) { boilSeed('folder'); push(); translate(230, 560); scale(fk);
      paint([[-70, -20], [-20, -20], [-5, -42], [72, -42], [72, 72], [-70, 72]], { wash: PAL.ochre, ink: PAL.ink, sw: 2.5 }); pop(); }
    for (let i = 0; i < 9; i++) { const em = ease(seg(lt, 2.0 + i * .06, 3.0 + i * .06));
      const gx = 430 + (i % 3) * 70, gy = 500 + ((i / 3) | 0) * 70, p = [lerp(230, gx, em), lerp(560, gy, em)];
      if (em > .05) dot(p[0], p[1], 15, FAM[i % 3], 400 + i, { glowK: .4 * seg(lt, 3.6, 5.2) }); }
    const rk = seg(lt, 3.8, 4.8); if (rk > 0 && rk < 1) { boilSeed('Dring'); const rr = 40 + 110 * ease(rk); inkLine(ellPts(500, 570, rr, rr * .85, 26).concat([ellPts(500, 570, rr, rr * .85, 26)[0]]), 3 * (1 - rk), PAL.teal, 'ink', 1); }
    const arrowK = ease(seg(lt, 5.2, 6.2));
    if (arrowK > 0) { boilSeed('arrow'); inkLine([[640, 570], [640 + 150 * arrowK, 570]], 7, PAL.ink, 'ink'); if (arrowK > .8) paint([[790, 552], [822, 570], [790, 588]], { wash: PAL.ink, ink: null }); }
    const agentK = backOut(Math.min(1, seg(lt, 5.8, 6.8) * 1.3));
    if (agentK > .02) { boilSeed('agent'); push(); translate(885, 560); scale(agentK);
      paint(rrPts(-72, -72, 144, 144, 24, 2), { wash: TERM, ink: PAL.ink, sw: 2.5 });
      paint(starPts(0, -4, 36, .45, 4, .2), { wash: mixCol(PAL.cream, PAL.teal, .3), ink: null }); pop(); }
    call('your agent', 885, 710, 36, mixCol(PAL.ink, PAL.cream, .1), lt, 6.4, 0);
    clawd(150, 1000, 22, emotions(lt, [[0, 'happy', { lookX: .4, lookY: -.2 }], [3.8, 'proud', { lookX: .3, lookY: -.3 }]]));
    camEnd();
    boom('use the SKILL', CX, 175, 66, PAL.cream, PAL.teal, lt, .3, 2.2, { rot: -.03, burst: true });
    call('indexes your folder', CX, 200, 48, PAL.ink, lt, 2.4, 3.7, { rot: .01 });
    boom('by MEANING', CX, 185, 78, PAL.cream, PAL.clay, lt, 3.8, 5.3, { rot: -.04, burst: true });
    call('best matches → your agent', CX, 200, 44, PAL.ink, lt, 6.4, 0, { rot: 0 });
    if (lt < .28) brushWipe(.5 + lt / .56, [TERM, mixCol(PAL.indigo, PAL.cream, .7)]);
    if (lt > dur - .28) brushWipe((lt - (dur - .28)) / .56, [mixCol(PAL.indigo, PAL.cream, .7), PAL.night]);
  }

  // ============================================================ E: analytics (19.94–23.33)
  function shotE(t, lt, dur) {
    camBegin(CX, CY, 1.03);
    boilSeed('Ebg'); paint(rectPts(-400, -400, W + 800, H + 800), { wash: PAL.night, ink: null });
    for (let i = 0; i < 22; i++) { boilSeed('Est' + i); const tw = .5 + .5 * Math.sin(lt * (1.5 + hash(i)) + i * 2); paint(starPts(hash(i) * W, hash(i + 50) * H, 3 + 3 * hash(i + 9) * tw, .4, 4), { wash: PAL.cream, washOp: 110 * tw, ink: null }); }
    if (lt < 1.7) {
      for (let i = 0; i < 9; i++) { const f = i % 3, c = [[330, 560], [560, 500], [780, 580]][f]; const a = hash(i * 5) * TAU, r = 60 * ease(seg(lt, .2, 1.0)); dot(c[0] + Math.cos(a) * r, c[1] + Math.sin(a) * r * .8, 22, FAM[f], 300 + i, { glowK: .4 }); }
      cmd('sem cluster', CX, 250, 44, lt, .1, 1.7);
      boom('"cluster these!"', CX, 840, 58, PAL.night, PAL.teal, lt, .4, 1.7, { rot: -.03 });
    } else {
      for (let i = 0; i < 8; i++) { const a = hash(i) * TAU; dot(600 + Math.cos(a) * 150, 540 + Math.sin(a) * 120, 20, FAM[i % 3], 320 + i, { glowK: .35 }); }
      const ob = .5 + .5 * Math.abs(Math.sin(lt * 6)); glow(250, 720, 90 * ob, PAL.violet, .5); dot(250, 720, 24, PAL.violet, 340, { eyes: true, lookX: .6 });
      flag(300, 736, 86, seg(lt, 2.0, 3.0));
      cmd('sem outliers', CX, 250, 44, lt, 1.8, 0);
      boom('"the odd one out?"', CX, 860, 52, PAL.night, PAL.ochre, lt, 2.0, 0, { rot: .02 });
    }
    clawd(120, 1000, 18, feel(lt < 1.7 ? 'proud' : 'mischief', t));
    camEnd();
    if (lt < .28) brushWipe(.5 + lt / .56, [mixCol(PAL.indigo, PAL.cream, .7), PAL.night]);
    if (lt > dur - .28) brushWipe((lt - (dur - .28)) / .56, [PAL.night, SAND]);
  }

  // ============================================================ F: sandbox + outro (23.33–30)
  function shotF(t, lt, dur) {
    camBegin(CX, CY + 30 * (1 - ease(seg(lt, 0, 1.2))), 1.04);
    sandbox(seg(lt, 2.6, 4.4) * .8);
    const con = seg(lt, 2.8, 4.2);
    if (con > 0) for (let i = 0; i < 9; i++) { boilSeed('con' + i); const x = 180 + (i / 8) * 720 + 30 * Math.sin(i * 2.2), y = 180 + 120 * Math.sin(i / 9 * Math.PI) * (i % 2 ? -1 : 1) * .5 + 50 * hash(i); const tw = .6 + .4 * Math.sin(lt * 1.4 + i); glow(x, y, 50 * tw * con, FAM[i % 3], .5 * con); dot(x, y, (7 + 3 * hash(i)) * con, FAM[i % 3], 900 + i, {}); }
    starfish(150, 828, 34); pail(940, 838, 78);
    const mood = emotions(lt, [[0, 'happy', { lookX: .3, lookY: .3 }], [.6, 'surprised', { lookX: .8 }], [1.8, 'cool', { lookX: .5 }], [3.0, 'love', { lookY: -.3 }]]);
    const pin = seg(lt, .5, 1.1), pgone = seg(lt, 1.7, 2.1);
    if (pin > 0 && pgone < 1) { const px = kf(lt, [[.5, 1080], [1.1, 820]], ease); push(); if (pgone > 0) { translate(820, 720); scale(1 - pgone); translate(-820, -720); } phone(px, 720, 82, { ring: lt > .6 && lt < 1.6 ? 1 : 0, droop: seg(lt, 1.4, 1.7) }); pop(); }
    poof(820, 710, 70, pgone);
    const waveK = lt > 2.6 ? Math.sin((lt - 2.6) * 6) : 0;
    clawd(CX, 900, 40, { ...mood, aR: lt > 2.4 ? 1.1 + .35 * waveK : kf(lt, [[0, .5], [.6, -.5]], ease), aL: -.35 });
    sandboxFrame();
    camEnd();
    boom('100% OFFLINE', CX, 250, 70, PAL.cream, PAL.teal, lt, .9, 2.6, { rot: -.03 });
    const fade = 1 - seg(lt, 5.6, 6.4);
    boom('smol-sim-search', CX, 330, 60, PAL.cream, PAL.clay, lt, 3.0, 0, { rot: -.02, beat: 1 });
    if (lt > 3.9 && fade > 0) letter('ask better questions.', CX, 425, 42, mixCol(PAL.cream, PAL.teal, .45), { pop: ease(seg(lt, 3.9, 4.6)), alpha: 220 * seg(lt, 3.9, 4.6) * fade });
    flushLetters();
    if (lt < .28) brushWipe(.5 + lt / .56, [PAL.night, SAND]);
    const ir = seg(lt, 6.0, 6.9); if (ir > 0) iris(CX, 720, lerp(1500, 0, ease(ir)), PAL.night);
  }

  shots([[0, shotA], [3.97, shotB], [8.32, shotC], [12.55, shotD], [19.94, shotE], [23.33, shotF]]);
})();
