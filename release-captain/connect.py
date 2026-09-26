from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

from trueforge_sdk import (
    AgentSpec,
    AskUserQuestionsConfig,
    DynamicSubAgentsConfig,
    GenerativeUiConfig,
    McpServer,
    Model,
    ModelParams,
    RuntimeConfig,
    SandboxConfig,
    SessionAgentNameRef,
    Skill,
    TrueForge,
    UserMessage,
)
from trueforge_sdk.types.compaction_config import CompactionConfig
from trueforge_sdk.types.context_management_config import ContextManagementConfig
from trueforge_sdk.types.large_tool_response_config import LargeToolResponseConfig


client = TrueForge(
    base_url=os.environ.get("TRUEFORGE_BASE_URL", "http://localhost:8790"),
    token=os.environ.get("TRUEFORGE_TOKEN"),
    timeout=600,
)

PROJECT_ROOT = Path(__file__).resolve().parent


def _env_flag(name: str, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def sandbox_enabled() -> bool:
    return _env_flag("RELEASE_CAPTAIN_SANDBOX_ENABLED", _env_flag("TRUEFORGE_SANDBOX_ENABLED", False))


def build_agent_instructions() -> str:
    instructions = (PROJECT_ROOT / "agent" / "system_prompt.md").read_text()
    if sandbox_enabled():
        return instructions
    return (
        f"{instructions}\n\n"
        "Runtime override:\n"
        "- Sandbox execution is currently disabled.\n"
        "- Operate in analysis-only mode.\n"
        "- Do not attempt repository test execution.\n"
        "- Explicitly report test evidence as unavailable because sandbox execution is disabled.\n"
    )


def _configured_mcp_names() -> set[str]:
    return {server.name for server in client.mcp_servers.list().data}


def _configured_skill_names() -> set[str]:
    return {skill.name for skill in client.skills.list().data}


def build_agent_spec() -> AgentSpec:
    """Build the verified SDK representation of trueforge.yaml."""
    mcp_servers = []
    if "github" in _configured_mcp_names():
        mcp_servers.append(
            McpServer(
                name="github",
                enable_tools=["@all"],
                require_approval_for_tools=[
                    "@destructive",
                    "create_tag",
                    "create_release",
                    "merge_pull_request",
                ],
                preload=False,
            )
        )
    skills = [Skill(name="release-engineering")] if "release-engineering" in _configured_skill_names() else []
    return AgentSpec(
        model=Model(
            name=os.environ.get("TRUEFORGE_MODEL", "openai/gpt-5-4-mini"),
            params=ModelParams(temperature=0.1, max_tokens=4096),
        ),
        instructions=build_agent_instructions(),
        mcp_servers=mcp_servers,
        skills=skills,
        config=RuntimeConfig(
            sandbox=SandboxConfig(enabled=sandbox_enabled()),
            dynamic_sub_agents=DynamicSubAgentsConfig(enabled=True),
            generative_ui=GenerativeUiConfig(enabled=True),
            ask_user_questions=AskUserQuestionsConfig(enabled=True),
            context_management=ContextManagementConfig(
                compaction=CompactionConfig(enabled=True),
                large_tool_response=LargeToolResponseConfig(enabled=True),
            ),
            iteration_limit=80,
        ),
    )


def register_release_captain():
    """Register the named agent in TrueForge."""
    return client.agents.create(
        name="release-captain",
        description="Autonomous release engineering agent with approval gates.",
        manifest=build_agent_spec(),
    )


def sync_release_captain():
    """Create or update the named agent in TrueForge."""
    for agent in client.agents.list():
        if agent.name == "release-captain":
            return client.agents.update(
                agent_id=agent.id,
                manifest=build_agent_spec(),
                description="Autonomous release engineering agent with approval gates.",
            )
    return register_release_captain()


def create_release_session():
    """Create a persistent TrueForge session bound to the named agent."""
    return client.sessions.create(agent=SessionAgentNameRef(name="release-captain"))


def stream_release_analysis(
    session_id: str,
    repository_url: str,
    branch: str,
    previous_tag: str | None = None,
) -> Iterator[object]:
    """Stream analysis events; the caller handles approval-required events."""
    analysis_mode = "with sandbox test execution enabled" if sandbox_enabled() else "in analysis-only mode with sandbox test execution disabled"
    prompt = (
        f"Analyze repository {repository_url} from tag {previous_tag or 'the latest release'} "
        f"on branch {branch}. Operate {analysis_mode}. Use GitHub tools to inspect the repository directly, "
        "collect commits, pull requests, changed files, tags, and CI evidence, prepare release notes, "
        "and stop before any destructive action for human approval. "
        "If sandbox execution is disabled, explicitly mark tests as unavailable instead of trying to run them. "
        "If no previous tag exists, state the fallback baseline clearly."
    )
    return iter(
        client.sessions.create_turn_stream(
            session_id=session_id,
            input=[UserMessage(content=prompt)],
        )
    )
