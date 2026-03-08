# Nira Folder Merge Report

Date: 2026-03-04
Workspace: `C:\Users\JASHWANTH\NIRAmini`

## Merge strategy

- Source folders: `nira` and `nira_agent`
- Target folder: `nira_merged`
- `nira_agent` files were applied last for same-path conflicts (newer snapshot).
- Conflicting `nira` versions were preserved under `_conflicts/from_nira/*.from_nira`.
- `__pycache__` files were excluded.

## Comparison summary

- Files only in `nira`: 22
- Files only in `nira_agent`: 45
- Same-path files with different content: 14
- Total merged non-`__pycache__` files: 81

## Same-path conflicts (kept from `nira_agent`, archived from `nira`)

- `__init__.py`
- `__main__.py`
- `ai/__init__.py`
- `automation/__init__.py`
- `config.py`
- `main.py`
- `memory/__init__.py`
- `memory/preferences.py`
- `monitoring/__init__.py`
- `README.md`
- `requirements.txt`
- `security/__init__.py`
- `security/encryption.py`
- `ui/__init__.py`

## Files only in `nira`

- `ai/intent_parser.py`
- `ai/llm_connector.py`
- `ai/prompts.py`
- `automation/command_executor.py`
- `automation/dsl_parser.py`
- `automation/undo_stack.py`
- `automation/workflow_engine.py`
- `memory/action_log.py`
- `monitoring/activity_tracker.py`
- `monitoring/proactive_logic.py`
- `scripts/build_exe.ps1`
- `scripts/install.ps1`
- `scripts/run_dev.ps1`
- `security/passphrase.py`
- `security/voice_lock.py`
- `ui/animation.py`
- `ui/overlay.py`
- `ui/tray.py`
- `voice/__init__.py`
- `voice/speech_to_text.py`
- `voice/tts.py`
- `voice/wake_word.py`

## Files only in `nira_agent`

- `ai/confidence.py`
- `ai/llm_client.py`
- `ai/personality.py`
- `ai/prompting.py`
- `ai/structured_output.py`
- `automation/builtins.py`
- `automation/example_registry.py`
- `automation/executor.py`
- `automation/manager.py`
- `automation/models.py`
- `automation/permissions.py`
- `automation/skill_loader.py`
- `automation/tool_registry.py`
- `automation/undo.py`
- `automation/workflow_dsl.py`
- `logging_setup.py`
- `memory/compressor.py`
- `memory/context_builder.py`
- `memory/long_term.py`
- `memory/manager.py`
- `memory/short_term.py`
- `monitoring/activity.py`
- `monitoring/proactive.py`
- `monitoring/triggers.py`
- `performance.py`
- `routing/__init__.py`
- `routing/cache.py`
- `routing/hybrid_router.py`
- `routing/response_parser.py`
- `scripts/run.ps1`
- `security/audit.py`
- `security/auth.py`
- `security/tier_policy.py`
- `skills/__init__.py`
- `skills/app_skill.py`
- `skills/base.py`
- `skills/browser_skill.py`
- `skills/file_skill.py`
- `skills/ocr_skill.py`
- `skills/workflow_skill.py`
- `storage/__init__.py`
- `storage/sql_store.py`
- `system_validation.py`
- `ui/app_state.py`
- `workflows.dsl`
