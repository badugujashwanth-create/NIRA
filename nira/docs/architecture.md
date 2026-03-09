# NIRA Local Runtime Architecture

## Agent Runtime
`nira/core/agent_runtime.py` is the canonical orchestration layer. It receives user input, builds `AgentState`, gathers memory hits, selects the active role agent, builds a task graph, executes tasks, records monitoring data, updates memory, and returns a structured `RuntimeResponse`.

## Task Graph System
The task graph lives in `nira/task_graph/`. `TaskNode` is the serializable execution unit and contains `task_id`, `description`, `tool`, `status`, and `dependencies`. `TaskGraphPlanner` converts high-level intent into executable graphs, including the built-in `research_topic` workflow. `TaskGraphExecutor` advances ready nodes in dependency order, records each `ToolResult`, and uses `RepairLoop` for one bounded retry when a node fails.

## Memory Architecture
The runtime uses persistent local memory under `nira/memory/`.

- `short_term_memory.py` keeps the recent rolling conversation state in memory.
- `vector_store.py` stores semantic or lexical retrieval entries for conversations, research summaries, project context, and prior fixes in SQLite.
- `research_memory.py` stores topic summaries, key concepts, references, and report locations for later retrieval.
- `knowledge_graph.py`, `workflow_memory.py`, and `error_memory.py` store topic relationships, successful workflows, and prior failures or repairs for reuse.

## Research And Knowledge Engine
The deep research subsystem lives in `nira/research/`.

- `topic_planner.py` converts a user request into a structured topic plan with subtopics and research questions.
- `source_analyzer.py` collects local source text, extracts key concepts, and identifies important findings.
- `summarizer.py` chunks and compresses large research corpora for storage.
- `report_generator.py` writes structured research reports and metadata.

Research execution uses the task-graph workflow:
`plan_topic -> analyze_sources -> summarize_information -> generate_report -> store_knowledge`

The `store_knowledge` step persists results into research memory, vector memory, and the knowledge graph so future questions can retrieve prior research.

## Tool Framework
The tool framework lives in `nira/tools/`. Every concrete tool implements `Tool.run(args, state) -> ToolResult`. `ToolRegistry` is the single execution surface for the task graph and runtime. The default registry is local-first and includes project analysis, dependency updates, config edits, code generation, build execution, document editing, source browsing, research planning, research analysis, report generation, and knowledge storage.

## Document Processing
The document subsystem lives in `nira/documents/`.

- `pdf_processor.py` extracts and chunks PDF text locally.
- `text_extractor.py` normalizes extraction across markdown, text, code, config files, and PDFs.
- `document_creator.py`, `document_editor.py`, and `format_converter.py` support local authoring and conversion workflows.

## Local Model Runtime
`nira/models/llama_runtime.py` provides `LocalModel.generate(prompt)` and optional embedding support. It connects to a locally running llama.cpp server or can manage the server process directly using the existing `local_llm/llama_cpp_server.py` helper. No external API keys are required.
