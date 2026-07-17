# Recording guide

## Preparation

1. Install dependencies using docs/DEVELOPMENT.md.
2. Copy example environment files and use only local or synthetic values.
3. Start the demo with scripts/run-demo.ps1 or the component-specific command.
4. Confirm the complete workflow manually before recording.
5. Close notifications, unrelated applications, password managers, and personal browser profiles.

## Record

This project needs a terminal or desktop recorder. Follow DEMO_SCRIPT.md; capture at 720p or 1080p and keep commands readable. The current machine did not have FFmpeg or a terminal recorder, so no video is claimed here.

## Post-production

Trim loading time only; do not splice in fake success states. Add demo-captions.vtt. If FFmpeg is available, create a compressed MP4 and preview GIF, then verify size and readability. Never commit a large raw capture.

