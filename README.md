# 🌸 Cherry Drama — AI Movie Recap System

> Automatically generate professional movie recap videos with narrator voiceover, burned-in subtitles, and branded watermark — in Myanmar and Japanese.

---

## What This Project Does

Cherry Drama is a web-based AI pipeline that takes a raw movie/drama video file and produces a fully edited **recap video** with:

- Narrator voiceover (Myanmar or Japanese)
- Subtitles burned into the video
- Relevant scene clips from the original video synchronized to the narration
- Copyright transformation (speed/pitch/color adjustments)
- Animated Cherry Drama logo watermark
- Auto-generated movie poster-style thumbnail

Users supply their own AI API keys through the settings UI — no keys are hardcoded.

---

## Target Output

```
Input:  Full movie/drama video file (MP4, MKV, etc.)
Output: Recap video (3–10 min, AI-recommended duration)
        + Thumbnail image (movie poster style)
```

Output structure:
```
[0:00–0:15]  HOOK       — AI-selected most dramatic moment (spoiler teaser)
[0:15–0:20]  INTRO      — Cherry Drama logo slide-in + movie title
[0:20–END]   RECAP      — Full story summary with clips + narrator + subtitles
[LAST 10s]   OUTRO      — Cherry Drama branded end card
```

Output includes:
- Hook: AI auto-detects the most shocking/emotional scene → 15s teaser
- Narrator speaks an engaging story summary
- Original movie clips edited to match narration
- Myanmar or Japanese subtitles burned in
- Cherry Drama logo (slide-in → corner watermark)
- Copyright-safe transformations applied

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        Frontend (React + Vite)          │
│  - Video upload                                         │
│  - Language selection (Myanmar / Japanese)              │
│  - API key settings page                                │
│  - Processing queue & progress tracker                  │
│  - Recap preview before export                          │
│  - History / library of past recaps                     │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP
┌────────────────────▼────────────────────────────────────┐
│                     Backend (Python FastAPI)            │
│                                                         │
│  Step 1: Transcription                                  │
│    └─ Whisper (via Groq API) → SRT with timestamps      │
│                                                         │
│  Step 2: Scene Analysis (Hybrid)                        │
│    └─ FFmpeg → key frames (every 60s)                   │
│    └─ Gemini Vision → visual scene description          │
│    └─ Merge: SRT dialogue + visual context              │
│                                                         │
│  Step 3: Recap Script Generation                        │
│    └─ Gemini 2.0 Flash                                  │
│    └─ AI detects most dramatic/emotional moment → Hook  │
│    └─ Output: [Hook 15s] + [Recap body]                 │
│               + scene timestamp mapping                 │
│    └─ AI recommends recap duration based on movie tempo │
│                                                         │
│  Step 4: Text-to-Speech                                 │
│    └─ Myanmar  → Google Cloud TTS (my-MM)               │
│    └─ Japanese → Voicevox (local, free)                 │
│                                                         │
│  Step 5: Video Composition (FFmpeg + MoviePy)           │
│    └─ Extract scene clips by timestamp                  │
│    └─ Concatenate clips                                 │
│    └─ Replace audio with narrator TTS                   │
│    └─ Burn subtitles (ASS format)                       │
│    └─ Apply copyright transforms:                       │
│         speed ±5%, pitch shift, color grade, crop 2%   │
│    └─ Add optional background music                     │
│    └─ Overlay Cherry Drama logo:                        │
│         slide-in from left (2s) → top-right corner     │
│         semi-transparent (70% opacity)                  │
│                                                         │
│  Step 6: Thumbnail Generation (Pillow)                  │
│    └─ Extract best frame from movie                     │
│    └─ Dark gradient overlay                             │
│    └─ Movie title text                                  │
│    └─ Cherry Drama logo + "Recap" badge                 │
│    └─ Export as JPG (1280x720)                          │
└─────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite + TypeScript |
| Backend | Python 3.11 + FastAPI |
| Transcription | Whisper via Groq API |
| Scene Analysis | FFmpeg (frames) + Gemini Vision |
| Recap AI | Gemini 2.0 Flash |
| Myanmar TTS | Google Cloud Text-to-Speech (my-MM) |
| Japanese TTS | Voicevox (open source, local) |
| Video Processing | FFmpeg + MoviePy |
| Thumbnail | Pillow (Python) |
| Subtitle Format | ASS (Advanced SubStation Alpha) |

---

## API Keys Required (User-supplied via Settings UI)

| Service | Purpose | Free Tier |
|---|---|---|
| **Groq API** | Whisper transcription | ✅ Free tier |
| **Gemini API** | Scene analysis + recap script | ✅ 1500 req/day |
| **Google Cloud TTS** | Myanmar narrator voice | ✅ 1M chars/month |

> Voicevox (Japanese TTS) runs locally — no API key needed.

---

## Features

### Core
- [x] Video upload (MP4, MKV, AVI, MOV)
- [x] Language selection: Myanmar / Japanese
- [x] Hybrid transcription (Whisper SRT + key frame vision)
- [x] AI recap script with narrator-style writing
- [x] AI-recommended recap duration based on movie tempo
- [x] TTS narrator audio generation
- [x] Scene clip extraction + synchronization
- [x] Subtitle burn-in
- [x] Copyright transformation (speed/pitch/color)
- [x] Cherry Drama animated logo watermark
- [x] Movie poster-style thumbnail
- [x] AI-generated Hook (opening 15s spoiler teaser)

### Enhanced
- [x] Processing queue (multiple videos)
- [x] Recap preview before final export
- [x] History / library of past recaps
- [x] Background music overlay (optional)
- [x] YouTube chapter markers (timestamps)
- [x] Multi-format export: YouTube (16:9), TikTok (9:16), Instagram (1:1)
- [x] Custom intro/outro clips
- [x] User API key settings page (keys never stored server-side)

---

## Project Structure

```
cherry-drama/
├── frontend/                  # React + Vite
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Home.tsx           # Upload + language select
│   │   │   ├── Processing.tsx     # Queue + progress
│   │   │   ├── Preview.tsx        # Recap preview
│   │   │   ├── Library.tsx        # Past recaps
│   │   │   └── Settings.tsx       # API key management
│   │   └── components/
├── backend/                   # Python FastAPI
│   ├── main.py
│   ├── routers/
│   │   ├── upload.py
│   │   ├── transcribe.py
│   │   ├── recap.py
│   │   ├── tts.py
│   │   ├── compose.py
│   │   └── thumbnail.py
│   ├── services/
│   │   ├── whisper_service.py
│   │   ├── gemini_service.py
│   │   ├── tts_myanmar.py
│   │   ├── tts_japanese.py        # Voicevox
│   │   ├── video_composer.py      # FFmpeg + MoviePy
│   │   └── thumbnail_generator.py # Pillow
│   └── assets/
│       └── cherrydrama_logo.png
├── voicevox/                  # Voicevox local server
└── README.md
```

---

## How to Run Locally

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/cherry-drama.git
cd cherry-drama

# 2. Install Python dependencies
pip install -r backend/requirements.txt

# 3. Start Voicevox (Japanese TTS) - optional
./voicevox/run.sh

# 4. Start backend
uvicorn backend.main:app --reload --port 8000

# 5. Start frontend
cd frontend
pnpm install
pnpm dev
```

---

## Copyright Approach

This system applies **Option A** transformations to help reduce automatic content fingerprint matching:

- Video speed adjusted ±5%
- Audio pitch shifted
- Color grading applied
- 2% border crop
- Cherry Drama logo watermark embedded throughout

> **Disclaimer:** These transformations assist with platform fingerprinting but do not constitute legal advice. Use only with content you have rights to, or under fair use / commentary doctrine in your jurisdiction. Cherry Drama logo branding adds attribution for dispute purposes.

---

## Roadmap

- [ ] Multi-episode batch processing (drama series)
- [ ] Custom narrator voice cloning (user's own voice)
- [ ] Auto-upload to YouTube via API
- [ ] Engagement-optimized title + description generator
- [ ] Analytics dashboard (views, CTR per recap)

---

## Brand

**Cherry Drama** — Myanmar & Japanese drama recap channel  
Logo: `assets/cherrydrama_logo.png`  
Colors: `#C2185B` (cherry pink), `#1a0a0f` (deep dark)

---

*Built with ❤️ for drama lovers everywhere.*
