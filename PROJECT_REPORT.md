# NIRA Project Report

## Current Runtime Status

NIRA currently runs through the Stage 3 autonomous entry point in [main.py](c:/Users/JASHWANTH/NIRAmini/main.py). The root runtime is backed by:

- [config/settings.py](c:/Users/JASHWANTH/NIRAmini/config/settings.py)
- [config/logger.py](c:/Users/JASHWANTH/NIRAmini/config/logger.py)
- [core/platform.py](c:/Users/JASHWANTH/NIRAmini/core/platform.py)

Legacy packages under `nira/` remain present for compatibility, but the active Stage 3 execution path is the root-level `config/`, `core/`, and `plugins/` architecture.

## Execution Transcript

Command executed locally:

```bash
python main.py
```

Scripted interactive session:

```text
NIRA Stage 3 interactive mode. Use /goal <task>, /metrics, /knowledge, /quit.
You> /goal schedule calendar review for tomorrow
NIRA> Goal complete. Prepared a calendar scheduling workflow for: schedule calendar review for tomorrow. Connect a calendar backend or plugin to execute it.
You> /metrics
{'counters': {'goals.executed': 1, 'agent.conversation.runs': 2, 'agent.planning.runs': 1, 'agent.automation.runs': 1}, 'timings': {}}
You> /knowledge
[]
You> /quit
```

The runtime also emitted structured JSON logs for startup, agent selection, and task completion.

## Main Features

### Stage 3 Autonomous Runtime

- Multi-step goal execution via [core/autonomy/goal_executor.py](c:/Users/JASHWANTH/NIRAmini/core/autonomy/goal_executor.py)
- Task tracking via [core/autonomy/task_manager.py](c:/Users/JASHWANTH/NIRAmini/core/autonomy/task_manager.py)
- Goal planning via [core/reasoning/planner.py](c:/Users/JASHWANTH/NIRAmini/core/reasoning/planner.py)
- Agent decision routing via [core/reasoning/decision_engine.py](c:/Users/JASHWANTH/NIRAmini/core/reasoning/decision_engine.py)

### Multi-Agent Coordination

- Coordinator: [core/agents/coordinator.py](c:/Users/JASHWANTH/NIRAmini/core/agents/coordinator.py)
- Specialist agents: [core/agents/specialists.py](c:/Users/JASHWANTH/NIRAmini/core/agents/specialists.py)
- Agent roles:
  - Conversation agent
  - Planning agent
  - Research agent
  - Automation agent
  - Memory/knowledge agent

### Research System

- Web search client: [core/research/web_search.py](c:/Users/JASHWANTH/NIRAmini/core/research/web_search.py)
- Content extraction and summarization: [core/research/content_parser.py](c:/Users/JASHWANTH/NIRAmini/core/research/content_parser.py)
- Research workflow: [core/research/research_agent.py](c:/Users/JASHWANTH/NIRAmini/core/research/research_agent.py)

### Knowledge Base

- Persistent knowledge storage: [core/knowledge/knowledge_base.py](c:/Users/JASHWANTH/NIRAmini/core/knowledge/knowledge_base.py)
- Lightweight semantic retrieval using token-hash embeddings and overlap scoring

### Plugins

- Plugin base: [plugins/base.py](c:/Users/JASHWANTH/NIRAmini/plugins/base.py)
- Plugin loader: [plugins/manager.py](c:/Users/JASHWANTH/NIRAmini/plugins/manager.py)
- Included plugins:
  - [plugins/weather_plugin.py](c:/Users/JASHWANTH/NIRAmini/plugins/weather_plugin.py)
  - [plugins/news_plugin.py](c:/Users/JASHWANTH/NIRAmini/plugins/news_plugin.py)
  - [plugins/calendar_plugin.py](c:/Users/JASHWANTH/NIRAmini/plugins/calendar_plugin.py)

### Monitoring

- Counters and timings: [core/monitoring/metrics.py](c:/Users/JASHWANTH/NIRAmini/core/monitoring/metrics.py)
- Structured JSON logging to console and `data/cache/nira_stage3.log`

## Project Structure

Top-level folders currently present:

```text
config/
core/
data/
desktop_app/
local_llm/
nira/
nira_agent/
nira_visual/
plugins/
tests/
```

Stage 3 runtime folders:

```text
config/
core/
plugins/
```

Legacy or auxiliary folders still present:

- `nira/`
- `nira_agent/`
- `local_llm/`
- `nira_visual/`
- `desktop_app/`

## Tests

Focused Stage 3 tests:

- [tests/test_planner.py](c:/Users/JASHWANTH/NIRAmini/tests/test_planner.py)
- [tests/test_knowledge_base.py](c:/Users/JASHWANTH/NIRAmini/tests/test_knowledge_base.py)
- [tests/test_goal_executor.py](c:/Users/JASHWANTH/NIRAmini/tests/test_goal_executor.py)

Command:

```bash
pytest tests/test_planner.py tests/test_knowledge_base.py tests/test_goal_executor.py
```

Status: passing.

## Current Limitations

- The research path depends on live network access for DuckDuckGo HTML search and page fetches.
- Automation is currently orchestration-oriented, not a full OS executor in Stage 3.
- Calendar, weather, and news plugins are stubs and need real backend integrations.
- Legacy folders are still present and not yet fully consolidated into one package tree.
