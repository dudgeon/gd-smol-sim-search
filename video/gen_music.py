"""Generate a bouncy music bed for the smol-sim-search video via OpenRouter Lyria.

Lyria returns short clips, so we generate a few, treat them as 48 kHz stereo s16le
PCM, and build a ~47 s bed by concatenating with short crossfades + fade in/out.
Writes vo/music_raw_N.wav and vo/music_bed.wav.
"""
import base64, json, os, subprocess, sys, urllib.request, wave

HERE = os.path.dirname(os.path.abspath(__file__))
FF = os.path.join(HERE, "..", "node_modules", "ffmpeg-static", "ffmpeg")
KEY = [l.split("=", 1)[1].strip() for l in open(os.path.expanduser("~/repos/gd-smol-sim-search/.env")) if l.startswith("OPENROUTER_API_KEY=")][0]
RATE, CH = 48000, 2

PROMPTS = [
 "Instrumental only, no vocals. Bouncy, cheerful, playful tech jingle. Marimba melody, plucky synth bass, hand claps, light shaker, bright major key, about 120 BPM. Cute friendly indie-app promo energy. Upbeat and looping.",
 "Instrumental only, no vocals. Same bouncy playful marimba-and-pluck groove, 120 BPM, major key, claps and shaker, a touch more melody on top. Cheerful, energetic, seamless loop.",
 "Instrumental only, no vocals. Bouncy playful marimba groove with a little triumphant lift, 120 BPM, major key, claps, glockenspiel sparkle. Cheerful indie-app promo finale, upbeat.",
]

def gen(prompt):
    body = json.dumps({"model": "google/lyria-3-pro-preview", "modalities": ["text", "audio"], "stream": True,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body,
                                 headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    pcm = bytearray()
    with urllib.request.urlopen(req, timeout=400) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                continue
            try:
                a = json.loads(line[5:]).get("choices", [{}])[0].get("delta", {}).get("audio") or {}
            except ValueError:
                a = {}
            if a.get("data"):
                pcm += base64.b64decode(a["data"])
    return bytes(pcm[: len(pcm) - (len(pcm) % (2 * CH))])   # align to full stereo frames

clips = []
for i, p in enumerate(PROMPTS):
    path = os.path.join(HERE, f"music_raw_{i}.wav")
    if not os.path.exists(path):
        print(f"lyria clip {i} ...", flush=True)
        pcm = gen(p)
        w = wave.open(path, "wb"); w.setnchannels(CH); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(pcm); w.close()
    d = wave.open(path); dur = d.getnframes() / d.getframerate()
    print(f"  clip {i}: {dur:.1f}s")
    clips.append((path, dur))

# Build a >=47s bed: repeat the clip sequence with 0.4s acrossfades, then trim + fades.
XF = 0.4
seq = []
total = 0.0
i = 0
while total < 48:
    seq.append(clips[i % len(clips)][0])
    total += clips[i % len(clips)][1] - XF
    i += 1

# chain acrossfades
cur = seq[0]
for j, nxt in enumerate(seq[1:], 1):
    out = os.path.join(HERE, f"_bed_{j}.wav")
    subprocess.run([FF, "-y", "-loglevel", "error", "-i", cur, "-i", nxt,
                    "-filter_complex", f"[0][1]acrossfade=d={XF}:c1=tri:c2=tri", out], check=True)
    cur = out
# trim to 47s and fade in/out
bed = os.path.join(HERE, "music_bed.wav")
subprocess.run([FF, "-y", "-loglevel", "error", "-i", cur, "-t", "47",
                "-af", "afade=t=in:st=0:d=1.0,afade=t=out:st=45.5:d=1.5", bed], check=True)
for f in os.listdir(HERE):
    if f.startswith("_bed_"):
        os.remove(os.path.join(HERE, f))
d = wave.open(bed); print(f"music_bed.wav: {d.getnframes()/d.getframerate():.1f}s @ {d.getframerate()} Hz {d.getnchannels()}ch")
