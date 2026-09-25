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
 ("hook",     "Keyword search only finds the words you already typed."),
 ("meet",     "Meet smol-sim-search. Tiny crab, big brain."),
 ("setup",    "Clone it, run setup once. That's the only download."),
 ("skill",    "Then just use the skill: it indexes your folder, searches by meaning, and hands the best matches to your agent."),
 ("analytics","Or just say: cluster these! ...which one's the odd one out?"),
 ("outro",    "All local. All offline. smol-sim-search — ask better questions."),
]

SYSTEM = ("You are a professional voice actor recording a scripted voiceover for a short, playful product video. "
          "Speak the user's script EXACTLY as written, verbatim — no greetings, no additions, no rewording. "
          "Begin the script IMMEDIATELY: never acknowledge these instructions, never say 'Understood' or 'Here we go'. "
          "This is a developer-tool voiceover, NOT a consumer ad: never invent product names, taglines, or ad copy. Read ONLY the exact words given, nothing else. "
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

GAP, LEAD, TAIL = 0.22, 0.30, 1.00
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
