"""Factory for creating and configuring Semantic Kernel agents with standardized settings."""

import logging
from typing import Optional, Dict, Any, List
from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
from semantic_kernel.functions import KernelFunction


class AgentFactory:
    """
    Factory for creating and configuring Semantic Kernel agents with standardized settings.
    Python equivalent of the C# AgentFactory with full feature parity.
    """

    def __init__(self, kernel: Kernel, logger: Optional[logging.Logger] = None):
        """Initialize the agent factory."""
        if kernel is None:
            raise ValueError("kernel cannot be None")

        self._kernel = kernel
        self._logger = logger or logging.getLogger(__name__)

    def create_chat_agent(
        self,
        name: str,
        instructions: str,
        description: Optional[str] = None,
        execution_settings: Optional[OpenAIChatPromptExecutionSettings] = None
    ) -> ChatCompletionAgent:
        """Create a chat completion agent with the specified configuration."""
        if not name:
            raise ValueError("name cannot be null or empty")

        self._logger.info(f"Creating chat agent: {name}")

        if execution_settings is None:
            execution_settings = OpenAIChatPromptExecutionSettings(
                temperature=0.7,
                max_tokens=2000,
                top_p=0.9,
                frequency_penalty=0.0,
                presence_penalty=0.0
            )

        agent = ChatCompletionAgent(
            service_id="default",
            kernel=self._kernel,
            name=name,
            instructions=instructions,
            description=description or f"A specialized agent named {name}",
            execution_settings=execution_settings
        )

        self._logger.info(f"Successfully created chat agent: {name}")
        return agent

    def create_document_analysis_agent(self) -> ChatCompletionAgent:
        """Create a specialized document analysis agent."""
        instructions = """
You are a specialized document analysis agent. Your responsibilities include:
- Analyzing document content for key information, sentiment, and structure
- Extracting relevant metadata and insights
- Identifying potential issues or inconsistencies
- Providing structured summaries and recommendations

Always provide clear, structured responses with specific evidence from the documents.
When uncertain about document content, clearly state your confidence level.
        """.strip()

        execution_settings = OpenAIChatPromptExecutionSettings(
            temperature=0.3,  # Lower temperature for more consistent analysis
            max_tokens=3000,
            top_p=0.9
        )

        return self.create_chat_agent(
            name="DocumentAnalyst",
            instructions=instructions,
            description="Specialized agent for document analysis and content extraction",
            execution_settings=execution_settings
        )

    def create_approval_coordinator_agent(self) -> ChatCompletionAgent:
        """Create a specialized approval coordinator agent for HITL workflows."""
        instructions = """
You are an approval coordinator agent responsible for managing human-in-the-loop workflows.
Your responsibilities include:
- Evaluating requests that require human approval
- Determining the appropriate approval level and urgency
- Providing context and recommendations to human reviewers
- Tracking approval status and following up as needed
- Ensuring compliance with approval policies and procedures

Always provide clear summaries of what needs approval and why.
Include relevant risk assessments and business impact analysis.
Maintain a professional and helpful tone in all communications.
        """.strip()

        execution_settings = OpenAIChatPromptExecutionSettings(
            temperature=0.4,
            max_tokens=2500,
            top_p=0.9
        )

        return self.create_chat_agent(
            name="ApprovalCoordinator",
            instructions=instructions,
            description="Coordinates human approval workflows and manages escalation processes",
            execution_settings=execution_settings
        )

    def create_task_orchestrator_agent(self) -> ChatCompletionAgent:
        """Create a specialized task orchestrator agent for complex workflows."""
        instructions = """
You are a task orchestrator agent responsible for coordinating complex multi-step workflows.
Your responsibilities include:
- Breaking down complex tasks into manageable steps
- Coordinating between multiple specialized agents
- Managing task dependencies and execution order
- Monitoring progress and handling exceptions
- Providing status updates and summary reports

Focus on efficient task execution while maintaining quality and accuracy.
Escalate issues that require human intervention appropriately.
Maintain clear audit trails of all orchestration decisions.
        """.strip()

        execution_settings = OpenAIChatPromptExecutionSettings(
            temperature=0.5,
            max_tokens=2500,
            top_p=0.9
        )

        return self.create_chat_agent(
            name="TaskOrchestrator",
            instructions=instructions,
            description="Orchestrates complex multi-agent workflows and task coordination",
            execution_settings=execution_settings
        )

    def create_custom_agent(
        self,
        name: str,
        instructions: str,
        plugins: Optional[List[KernelFunction]] = None,
        execution_settings: Optional[OpenAIChatPromptExecutionSettings] = None
    ) -> ChatCompletionAgent:
        """Create a custom agent with user-defined tools and capabilities."""
        self._logger.info(f"Creating custom agent with plugins: {name}")

        # Add plugins to the kernel if provided
        if plugins:
            for plugin in plugins:
                self._kernel.add_function(plugin=plugin)
                self._logger.info(f"Added plugin {plugin.name} to agent {name}")

        if execution_settings is None:
            execution_settings = OpenAIChatPromptExecutionSettings(
                temperature=0.7,
                max_tokens=2000,
                top_p=0.9
            )

        return ChatCompletionAgent(
            service_id="default",
            kernel=self._kernel,
            name=name,
            instructions=instructions,
            description=f"Custom agent: {name}",
            execution_settings=execution_settings
        )