from __future__ import annotations


def build_user_prompt(user_input: str, context_block: str, tool_whitelist: list[str]) -> str:
    tools = ", ".join(tool_whitelist)
    return (
        f"User input: {user_input}\n\n"
        f"Context:\n{context_block}\n\n"
        f"Available tools (whitelist): {tools}\n"
        "If a tool is needed, return strict JSON with tool_calls array.\n"
        "If no tool is needed, set tool_calls to [].\n"
    )


def build_phase1_planning_prompt(user_input: str, context_block: str, tool_whitelist: list[str]) -> str:
    tools = ", ".join(tool_whitelist)
    return (
        "PHASE 1 (PLANNING): Produce a concise execution plan.\n"
        "Return strict JSON with keys: message, tool_calls, confidence.\n"
        "message must describe plan intent in 1-2 lines.\n"
        "tool_calls should include only whitelisted tools if needed.\n"
        f"Whitelisted tools: {tools}\n\n"
        f"User input:\n{user_input}\n\n"
        f"Context:\n{context_block}\n"
    )


def build_phase2_final_prompt(
    user_input: str,
    context_block: str,
    phase1_plan_message: str,
    tool_whitelist: list[str],
) -> str:
    tools = ", ".join(tool_whitelist)
    return (
        "PHASE 2 (FINAL): Return final strict JSON only.\n"
        "Required keys: message, tool_calls, confidence.\n"
        "Optional key: goal_achieved (boolean).\n"
        "Use plan from phase1; do not add unsupported keys.\n"
        f"Whitelisted tools: {tools}\n\n"
        f"Phase1 plan:\n{phase1_plan_message}\n\n"
        f"User input:\n{user_input}\n\n"
        f"Context:\n{context_block}\n"
    )


def build_reflection_prompt(user_input: str, tool_feedback: str, context_block: str) -> str:
    return (
        "REFLECTION PHASE: Determine whether user goal is achieved after tools.\n"
        "Return strict JSON with: message, tool_calls, confidence, goal_achieved.\n"
        "If goal is achieved: goal_achieved=true and tool_calls=[].\n"
        "If not achieved: goal_achieved=false and provide minimal corrective tool_calls.\n\n"
        f"Original user input:\n{user_input}\n\n"
        f"Tool feedback:\n{tool_feedback}\n\n"
        f"Context:\n{context_block}\n"
    )


def build_clarification_prompt(user_input: str) -> str:
    return (
        "I need clarification before proceeding safely. "
        f"Could you clarify your request: '{user_input}'? "
        "Please include exact app/file target and desired outcome."
    )
