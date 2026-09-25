"""Generate the smol-sim-search voiceover, one WAV per section, via OpenRouter gpt-audio.

Reads OPENROUTER_API_KEY from ~/repos/gd-smol-sim-search/.env. Writes vo/s01.wav..,
vo/timings.json (measured durations) and vo/voiceover.wav (concatenated with gaps).
"""
import base64, json, os, sys, time, urllib.request, wave, io

HERE = os.path.dirname(os.path.abspath(__file__))
for line in open(os.path.expanduser("~/repos/gd-smol-sim-search/.env")):
    if line.startswith("OPENROUTER_API_KEY="):
        KEY = line.split("=", 1)[1].strip()

SECTIONS = [
 ("hook",     "This is your repo. Somewhere in here... is the thing you're looking for. The catch? Grep only finds words you already know. Meaning? ...Not grep's department."),
 ("meet",     "Meet smol-sim-search! A search engine so small, it lives right inside your repo — and it finds things by what they mean."),
 ("install",  "Install? One clone. One setup script. No downloads, no dependencies — every last byte ships in the box. Batteries very much included."),
 ("anyrepo",  "Then, in any repo, just ask. First question? It indexes itself. Changed a file? It only re-reads the diff."),
 ("how",      "Under the hood, every chunk of text becomes a point in space. Similar meanings huddle close together. So searching is just... checking the neighborhood."),
 ("why",      "Which means 'charged twice' finds 'billed double'. Same idea, different words. And duplicates? Busted."),
 ("cluster",  "It'll also cluster your data into themes, flag the weird outliers, and map who's related to who. Tiny crab... big analytics."),
 ("sandbox",  "Best part? Fully local. Fully offline. It never phones home — it doesn't even have a phone. Which makes it perfectly happy inside a sandbox."),
 ("outro",    "smol-sim-search. Clone it... and start asking better questions."),
]

SYSTEM = ("You are a professional voice actor recording a scripted voiceover for a short, playful product video. "
          "Speak the user's script EXACTLY as written, verbatim — no greetings, no additions, no rewording. "
          "Begin the script IMMEDIATELY: never acknowledge these instructions, never say 'Understood' or 'Here we go'. "
          "Tone: warm, cheerful, lighthearted documentary narrator with a smile in the voice; upbeat but clear; "
          "medium-brisk pace with the comic pauses the ellipses suggest.")

RATE = 24000  # gpt-audio streams pcm16 mono at 24 kHz

def tts(text):
    body = json.dumps({
        "model": "openai/gpt-audio",
        "modalities": ["text", "audio"],
        "audio": {"voice": "coral", "format": "pcm16"},
        "stream": True,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": text}],
        "temperature": 0.6,
    }).encode()
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body,
                                 headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    pcm = bytearray()
    with urllib.request.urlopen(req, timeout=600) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                delta = json.loads(payload)["choices"][0].get("delta", {})
            except (ValueError, KeyError, IndexError):
                continue
            a = delta.get("audio") or {}
            if a.get("data"):
                pcm += base64.b64decode(a["data"])
    if not pcm:
        sys.exit("stream produced no audio")
    buf = io.BytesIO()
    w = wave.open(buf, "wb")
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
    w.writeframes(bytes(pcm)); w.close()
    return buf.getvalue()

def wav_params(b):
    w = wave.open(io.BytesIO(b))
    return w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()

GAP, LEAD, TAIL = 0.45, 0.50, 1.60
timings, clips = [], []
for name, text in SECTIONS:
    path = os.path.join(HERE, f"{name}.wav")
    if not os.path.exists(path):
        print(f"tts: {name} ...", flush=True)
        data = tts(text)
        open(path, "wb").write(data)
        time.sleep(1)
    b = open(path, "rb").read()
    rate, ch, sw, nf = wav_params(b)
    clips.append((name, b, nf / rate))
    print(f"  {name}: {nf/rate:.2f}s ({rate} Hz, {ch}ch)")

rate, ch, sw, _ = wav_params(clips[0][1])
out = wave.open(os.path.join(HERE, "voiceover.wav"), "wb")
out.setnchannels(ch); out.setsampwidth(sw); out.setframerate(rate)
def silence(sec): out.writeframes(b"\x00" * int(sec * rate) * ch * sw)
t = LEAD; silence(LEAD)
for name, b, dur in clips:
    w = wave.open(io.BytesIO(b)); out.writeframes(w.readframes(w.getnframes()))
    timings.append({"name": name, "start": round(t, 2), "end": round(t + dur, 2)})
    t += dur
    silence(GAP); t += GAP
silence(TAIL - GAP); t += TAIL - GAP
out.close()
json.dump({"total": round(t, 2), "sections": timings}, open(os.path.join(HERE, "timings.json"), "w"), indent=1)
print(f"total: {t:.2f}s -> voiceover.wav + timings.json")
