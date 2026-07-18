# NIRA v0.5 narration

NIRA is a local-first assistant built around a simple promise: useful planning and memory should not remove user control. This is the real version zero point five desktop. It starts in deterministic offline mode, stores conversations locally, and requires approval before workspace writes, processes, or network access.

The health view comes from the canonical runtime used by the desktop, console, module entry point, and command line. Only read access and NIRA-owned state are allowed by default. Interaction-training logs are off. The first chat response is intentionally honest: no local model is running. Project inspection, memory, planning, and permissioned workflows still remain available.

The Operations Center is a read-only window over that same runtime, not a presentation-only dashboard. Its overview counts the specialist roles, registered tools, workflow templates, local conversations, stored messages, and loaded models. The agent board shows which sequential roles handled the request: intent routing, the selected specialist, planning, safety review, permission-bound execution, critique, and response. The collaboration trace records completed handoffs without inventing parallel agents.

The memory tab reports the current local SQLite session, message counts, active context turns, and research records without displaying conversation content. Workflows show the registered template and the completed task-plan states from the last request. Model routing exposes configured aliases, cache limits, and the honest offline-safe state when no model is loaded. Tools and permissions list the real registry and the default read-and-state authority. System Health reports live process metrics and a privacy-safe contract that excludes the workspace path, state directory, and conversation identifier. Refresh only observes state; it never grants access.

Conversation history is SQLite on this device. The walkthrough creates synthetic sessions to demonstrate search, open, pin, rename, Markdown export, and confirmation-gated deletion. Restart recovery and context switching use the same store; there is no cloud sync claim.

Now NIRA invokes its first real tool. Project inspection reports source files, languages, and manifests while pruning virtual environments, dependency folders, caches, and build output. The second tool reads README content only inside the selected workspace and applies an output limit. A deliberate attempt to read dot-dot slash outside dot text is rejected by resolved-path containment. No outside file is opened.

The coding workflow demonstrates the important boundary. NIRA can inspect the repository and create a proposal in its own state, but a local verification command is a process side effect. The desktop names the tool, access class, and working directory. Deny is the focused default. Denying stops the graph and does not trigger a repair or a second permission prompt.

The decision evidence records the tool, access class, verdict, timestamp, and reason. Raw arguments are excluded so a secret in a command is not copied into the audit trail.

A second verification uses the same boundary. This time the narrow compile command is allowed once. Approval is not a permanent grant. When the process finishes, NIRA reports the actual task result.

Returning to the Workflows tab now shows the completed states from that real verification plan. The template registry and the last executed graph remain separate, so a configured workflow is never presented as proof that it ran.

The release candidate has fifty-one automated tests. Dependency auditing found no known vulnerabilities in the audited environment. Gitleaks found no tracked secrets in the current tree or full history. The version zero point five wheel also installed and returned healthy status output from outside the repository.

The limitations matter. The llama dot C P P adapter is configurable and mock-tested, but this release does not claim a verified real model or hardware profile. Voice, O C R, older PyQt features, retrieval quality, and screen-reader behavior remain outside the verified core. NIRA is a strong local prototype because its integrated operations are real, its side effects are explicit, and its unfinished areas are stated plainly.
