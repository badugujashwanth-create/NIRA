# Recording guide

## Automated authentic recording

```powershell
.\scripts\record-demo.ps1
```

The script verifies the full test suite, starts `python -m nira --full-demo` in a new temporary state directory, renders only windows owned by the NIRA process, generates Windows TTS narration when available, muxes WebM/Opus, creates a thumbnail and verification frames, and rejects output shorter than three minutes. Because it uses direct window rendering instead of desktop sampling, unrelated applications and virtual desktops cannot enter the video.

FFmpeg 8.1.2 is used from `NIRA_FFMPEG`, `PATH`, or a temporary GitHub release download from the Windows build provider linked by FFmpeg's official download page. It is not installed system-wide or committed.

## Manual preflight

- Confirm no `.env`, token, private URL, personal state directory, or browser content is visible.
- Use deterministic offline mode; do not start an unverified model for the release demo.

## Acceptance

- Duration at least 180 seconds; target approximately 245 seconds.
- 1280 x 720 output with VP9 video and Opus narration when available.
- First, middle, permission, and closing frames inspected.
- Captions cover the full story and match visible states.
- No edit implies a denied action or unavailable model succeeded.
