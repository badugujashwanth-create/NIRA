# NIRA v0.4 narration

NIRA is a local-first assistant built around a simple promise: useful planning and memory should not remove user control. This is the real version zero point four desktop. It starts in deterministic offline mode, stores conversations locally, and requires approval before workspace writes, processes, or network access.

The health view comes from the canonical runtime used by the desktop, console, module entry point, and command line. Only read access and NIRA-owned state are allowed by default. Interaction-training logs are off. The first chat response is intentionally honest: no local model is running. Project inspection, memory, planning, and permissioned workflows still remain available.

Conversation history is SQLite on this device. The walkthrough creates synthetic sessions to demonstrate search, open, pin, rename, Markdown export, and confirmation-gated deletion. Restart recovery and context switching use the same store; there is no cloud sync claim.

Now NIRA invokes its first real tool. Project inspection reports source files, languages, and manifests while pruning virtual environments, dependency folders, caches, and build output. The second tool reads README content only inside the selected workspace and applies an output limit. A deliberate attempt to read dot-dot slash outside dot text is rejected by resolved-path containment. No outside file is opened.

The coding workflow demonstrates the important boundary. NIRA can inspect the repository and create a proposal in its own state, but a local verification command is a process side effect. The desktop names the tool, access class, and working directory. Deny is the focused default. Denying stops the graph and does not trigger a repair or a second permission prompt.

The decision evidence records the tool, access class, verdict, timestamp, and reason. Raw arguments are excluded so a secret in a command is not copied into the audit trail.

A second verification uses the same boundary. This time the narrow compile command is allowed once. Approval is not a permanent grant. When the process finishes, NIRA reports the actual task result.

The release candidate has forty-nine automated tests. Dependency auditing found no known vulnerabilities in the audited environment. Gitleaks found no tracked secrets in the current tree or seventeen-commit history. The version zero point four wheel also installed and returned healthy output from outside the repository.

The limitations matter. The llama dot C P P adapter is configurable and mock-tested, but this release does not claim a verified real model or hardware profile. Voice, O C R, older PyQt features, retrieval quality, and screen-reader behavior remain outside the verified core. NIRA is a strong local prototype because its useful behavior is real, its side effects are explicit, and its unfinished areas are stated plainly.
