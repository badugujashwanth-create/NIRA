# Accessibility review

Status: in progress; no compliance claim  
Last reviewed: 18 July 2026

The corrected desktop flow was captured and reviewed in [the UI/UX audit](design/UI_UX_AUDIT.md). Windows DPI awareness, smaller widget requests, and a fixed layout row now keep the composer visible at the 1120 x 760 default. This is a resolved usability defect, not evidence of accessibility conformance.

## Confirmed from current evidence

- Text is not communicated by color alone in the captured task states.
- Primary controls use text labels rather than icon-only actions.
- The interface uses a consistent reading order: header, conversation, task progress, context, then composer in source order.
- Conversation and permission dialogs support Escape; conversation history supports Return and double-click; Ctrl+N, Ctrl+H, and Ctrl+L shortcuts are implemented.
- The process-permission dialog starts on the safe `Deny` action and identifies the tool and access class.
- Progress and completion changes are not exposed through a verified live-region or desktop accessibility announcement.

## Required before release

- Verify a complete keyboard-only flow, including conversation management and permission dialogs.
- Add and verify visible focus states for every interactive control.
- Confirm accessible names and roles with Windows Narrator or NVDA.
- Measure text and control contrast; do not infer passing ratios from screenshots.
- Test Windows text scaling, 200% scaling, high-contrast mode, and reduced viewport height.
- Verify the 960 x 640 minimum window on 100%, 125%, 150%, and 200% Windows scaling.
- Confirm that the search field, transcript, progress, context, and dialog controls expose useful accessible names and roles.

## Evidence limits

The present evidence is screenshot- and source-based. Keyboard behavior, assistive-technology output, contrast ratios, and platform scaling remain manual verification items. Full WCAG conformance is not claimed.
