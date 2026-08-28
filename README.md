# Voice Reader

A NiceGUI app: type a sentence, press **Listen**, and hear it read aloud — either
by one of your browser's built-in voices, or **in your own recorded voice**.

Built-in voices are spoken client-side with the Web Speech API. Recorded voices
are cloned server-side with [Coqui XTTS-v2](https://github.com/idiap/coqui-ai-TTS),
which runs entirely inside the container — no API keys, and no audio leaves the machine.

## Quick start

```bash
./start.sh
```

Then open http://localhost:8080

| Command | What it does |
| --- | --- |
| `./start.sh` | Build if needed and start in the background |
| `./start.sh --build` | Force an image rebuild, then start |
| `./start.sh --fg` | Run in the foreground, streaming logs |
| `./start.sh logs` | Follow the logs of the running container |
| `./start.sh stop` | Stop and remove the container |
| `./start.sh status` | Show the container status |
| `./start.sh restart` | Rebuild and restart |

## Pages

| Route | What it is |
| --- | --- |
| `/` | **Home** — type text, pick a voice, press Listen |
| `/voices` | **Voices** — the saved voice library as a table, with **Create voice** |

## Recording your voice

1. Go to **Voices** and press **Create voice**.
2. Name it, then press **Start recording** and read the passage aloud, to the end.
3. Press **Stop and save**. The dialog closes and the voice joins the table.
4. On **Home**, pick it from the **Voice** dropdown and press **Listen**.

A passage is provided to read because a cloned voice is only as good as its
reference: reading prepared text keeps you fluent and fills the clip with
connected speech covering a wide spread of sounds. **Another passage** cycles
through five of them.

The browser needs microphone permission; `getUserMedia` requires a secure context,
which `localhost` satisfies, so plain http works on the machine running Docker.

**The first synthesis is slow; later ones are not.** Measured on an Apple M4
(Docker, CPU-only — macOS has no GPU passthrough into containers):

| | Time |
| --- | --- |
| First ever call (downloads the ~1.8 GB model) | ~6 min |
| First call after a restart (loads model into memory) | ~25 s |
| Normal sentence, model already warm | ~10 s (real-time factor ≈ 2.2) |
| Text already spoken before | instant, served from cache |

The model download happens once and lives on the volume, so it survives rebuilds.

## Where recordings are stored

On the filesystem, in the `voice-data` Docker volume — one self-contained folder
per voice. Audio files are large and always read whole, so they are handed to
ffmpeg and the model by path rather than stored in a database.

```
/data/
├── voices/<voice-id>/
│   ├── meta.json      name, created-at, sample length
│   ├── sample.wav     normalised mono 24 kHz reference clip
│   └── source.webm    the untouched browser recording
├── models/            downloaded model weights
└── cache/             rendered clips, keyed by content hash
```

The volume survives image rebuilds, so neither your voices nor the model download
are lost on `./start.sh --build`.

## Theme

The interface follows the look of [Catalyst](https://catalyst-demo.tailwindui.com/):
a tinted sidebar beside a white content panel, zinc neutrals, hairline borders,
generous radii, stacked field labels, and a blue focus ring. Catalyst is a
commercial Tailwind UI package, so none of its component source is used here; the
look is rebuilt with plain CSS and Tailwind utilities in
[styles.css](app/static/css/styles.css).

Most of that stylesheet exists to tame Quasar. NiceGUI renders Quasar widgets,
which ship their own Material styling, so inputs, buttons, menus and the slider
have to be overridden at the component level — Tailwind classes on the Python side
cannot reach inside them. Layout and typography stay as `.classes(...)` utilities.

Light is the default. `VOICE_DARK=true` switches the same tokens to the dark palette.

## Project layout

```
.
├── start.sh                 # Docker entry point (start / stop / logs / status)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── app/
    ├── main.py              # wires static files, API, and pages; starts the server
    ├── config.py            # settings, overridable via environment variables
    ├── deps.py              # shared library + engine instances
    ├── api/routes.py        # REST endpoints for voices and synthesis
    ├── pages/
    │   ├── layout.py        # sidebar shell + field helper
    │   ├── home.py          # "/" - the reader
    │   └── voices.py        # "/voices" - table + create dialog
    ├── services/
    │   ├── audio.py         # ffmpeg normalisation and duration probing
    │   ├── library.py       # folder-backed voice library
    │   ├── speech.py        # Web Speech API snippets
    │   └── tts.py           # XTTS-v2 cloning, lazy-loaded and cached
    └── static/
        ├── css/styles.css
        └── js/
            ├── voices.js    # browser voice list helpers
            └── recorder.js  # microphone capture, upload, cloned playback
```

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/voices` | List stored voices |
| `POST` | `/api/voices` | Upload a recording (multipart: `name`, `file`) |
| `GET` | `/api/voices/{id}/sample` | Download the reference clip |
| `DELETE` | `/api/voices/{id}` | Delete a voice |
| `POST` | `/api/speak` | `{voice_id, text}` → WAV audio |
| `GET` | `/api/tts/status` | Model enabled / loaded / error |

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `VOICE_TITLE` | `Voice Reader` | Page and window title |
| `VOICE_HOST` | `0.0.0.0` | Bind address |
| `VOICE_PORT` | `8080` | Port (also the published host port) |
| `VOICE_DARK` | `false` | Dark palette instead of light |
| `VOICE_RELOAD` | `false` | NiceGUI auto-reload |
| `VOICE_DATA_DIR` | `/data` | Where voices, models, and cache live |
| `VOICE_TTS_MODEL` | `tts_models/multilingual/multi-dataset/xtts_v2` | Cloning model |
| `VOICE_TTS_LANGUAGE` | `en` | Synthesis language |
| `VOICE_TTS_ENABLED` | `true` | Set `false` to run browser-voices-only |

## Notes

- Browser voices come from the OS, so the built-in list differs per machine.
- The speed slider drives the utterance rate for browser voices and playback rate
  for cloned ones (0.5×–2×).
- XTTS-v2 is released under the [Coqui Public Model License](https://coqui.ai/cpml),
  which permits **non-commercial** use only.
- Requires a browser with Web Speech API and MediaRecorder support (Chrome, Edge, Safari).
