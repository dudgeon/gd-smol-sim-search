# The demo video — how it's made

`assets/smol-demo.mp4` is a ~100 s hand-painted short. This folder holds its source so it can be rebuilt.

## Pipeline

1. **Voiceover** — [`gen_vo.py`](gen_vo.py) sends the nine narration lines to OpenRouter's `openai/gpt-audio`
   (streaming PCM), trims each clip, and concatenates them with gaps into `voiceover.wav`, writing the measured
   per-section timings to [`vo-timings.json`](vo-timings.json). Needs `OPENROUTER_API_KEY` (kept in the repo-root
   `.env`, which is gitignored).
2. **Music** — [`gen_music.py`](gen_music.py) generates a bouncy instrumental with OpenRouter's `google/lyria-3-pro-preview`
   (which returns MP3), cuts a ~47 s bed with fades, then mixes it **under** the voiceover with sidechain ducking →
   `voiceover_music.wav` (the video's audio track).
3. **Storyboard** — [`STORYBOARD.md`](STORYBOARD.md): seven shots timed to the voiceover, one read at a time.
4. **Animation** — [`scene.smol.js`](scene.smol.js) is a [ClaudeAnimationBase](https://github.com/JohnHeibel/ClaudeAnimationBase)
   scene (p5.js + p5.brush), starring Clawd. Every frame is a pure function of time; the linework boils.
5. **Render** — frames → MP4 with the voiceover muxed in, then a 720p web pass (~7 MB).

## Rebuild

```bash
git clone https://github.com/JohnHeibel/ClaudeAnimationBase && cd ClaudeAnimationBase && npm install
cp ../smol-sim-search/video/scene.smol.js src/scenes/smol.js
cp ../smol-sim-search/video/gen_vo.py vo/gen_vo.py && python3 vo/gen_vo.py        # writes vo/voiceover.wav
# set PROJECT = { duration: 100.25, bpm: 96, offset: 0, audio: 'vo/voiceover.wav' } in src/config.js
# point studio.html's scene <script> at src/scenes/smol.js
node render.mjs --frames --workers=4
node render.mjs --encode --out=out/video.mp4 --audio=vo/voiceover_music.wav   # NB: --encode only muxes audio if --audio is passed
```

## Embedding it in the README

GitHub only plays a video **inline** in a README when the URL is a `user-attachments` one, which comes from
uploading the file through the browser — a raw committed-file URL is served as a download and the blob viewer
won't preview a file this size. So the committed README uses a poster image that links to the MP4 (works
everywhere), and the true inline player is an optional one-time manual step:

1. Open a new [issue](https://github.com/dudgeon/smol-sim-search/issues/new) (you don't have to submit it).
2. Drag `assets/smol-demo.mp4` into the comment box; wait for the upload to finish.
3. Copy the `https://github.com/user-attachments/assets/…` URL it inserts.
4. In `README.md`, replace the `<video>`/poster block under **See it in action** with that URL on its own line.
