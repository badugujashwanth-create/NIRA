# Desktop verification evidence manifest

Accepted current-build evidence:

- `01-empty-chat.png` - visible composer, empty state, offline mode, and privacy/status layout.
- `02-offline-response.png` - deterministic offline response and bounded project context.
- `03-permission-request.png` - custom default-deny process approval dialog.
- `04-permission-denied.png` - failed task and explicit blocked-process recovery message.
- `05-conversation-manager.png` - local session management controls.

`03-permission-dialog-missing.png` is retained troubleshooting evidence from a failed automation attempt. It is not an accepted product screenshot and is not used for UI or accessibility claims.

The recorder also compares the visible transcript with `ui-audit-transcript.txt` written only inside the temporary demo-state directory. This guards against accepting stale Windows child-control surfaces.
