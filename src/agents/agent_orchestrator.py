"""Orchestrator for managing multiple agents and their interactions using SK's built-in patterns."""

import asyncio
import logging
from typing import Dict, List, Optional, AsyncIterator, Callable, Any, Union
from semantic_kernel.agents import Agent, AgentGroupChat, ChatCompletionAgent
from semantic_kernel.contents import ChatMessageContent, AuthorRole
from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel.functions import KernelFunction
from semantic_kernel import Kernel


class AgentOrchestrator:
    """
    Orchestrator for managing multiple agents and their interactions.
    Python equivalent of the C# AgentOrchestrator with full feature parity.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the agent orchestrator."""
        self._logger = logger or logging.getLogger(__name__)
        self._agents: Dict[str, Agent] = {}
        self._group_chats: Dict[str, AgentGroupChat] = {}

    def register_agent(self, agent: Agent) -> None:
        """Register an agent with the orchestrator."""
        if not agent:
            raise ValueError("Agent cannot be None")

        self._agents[agent.name] = agent
        self._logger.info(f"Registered agent: {agent.name}")

    def create_group_chat(
        self,
        chat_id: str,
        agents: List[Agent],
        selection_strategy: Optional[KernelFunction] = None
    ) -> AgentGroupChat:
        """Create a group chat with specified agents using SK's AgentGroupChat."""
        if not agents:
            raise ValueError("At least one agent must be provided")

        self._logger.info(f"Creating group chat {chat_id} with {len(agents)} agents")

        # Create group chat with the agents
        group_chat = AgentGroupChat(*agents)

        # Configure execution settings if selection strategy provided
        if selection_strategy:
            # Note: Exact API may vary based on SK's Python implementation
            group_chat.execution_settings = {
                'selection_strategy': selection_strategy,
                'termination_strategy': self._create_default_termination_strategy()
            }

        # Store the group chat
        self._group_chats[chat_id] = group_chat

        for agent in agents:
            self._logger.debug(f"Added agent {agent.name} to group chat {chat_id}")

        return group_chat

    async def execute_sequential_workflow(
        self,
        agents: List[Agent],
        initial_message: str
    ) -> AsyncIterator[ChatMessageContent]:
        """Execute a sequential workflow where agents process tasks in order."""
        self._logger.info(f"Starting sequential workflow with {len(agents)} agents")

        current_message = initial_message

        for agent in agents:
            self._logger.debug(f"Processing with agent: {agent.name}")

            # Create chat history for this agent
            chat_history = ChatHistory()
            chat_history.add_user_message(current_message)

            # Get response from agent
            async for response in agent.invoke(chat_history):
                yield response

                # Use the agent's response as input for the next agent
                if response.role == AuthorRole.ASSISTANT:
                    current_message = response.content or ""

        self._logger.info("Sequential workflow completed")

    async def execute_concurrent_workflow(
        self,
        agents: List[Agent],
        message: str
    ) -> List[ChatMessageContent]:
        """Execute a concurrent workflow where multiple agents process the same task simultaneously."""
        self._logger.info(f"Starting concurrent workflow with {len(agents)} agents")

        async def process_with_agent(agent: Agent) -> List[ChatMessageContent]:
            """Process message with a single agent."""
            self._logger.debug(f"Starting concurrent processing with agent: {agent.name}")

            chat_history = ChatHistory()
            chat_history.add_user_message(message)

            responses = []
            async for response in agent.invoke(chat_history):
                responses.append(response)

            self._logger.debug(f"Completed concurrent processing with agent: {agent.name}")
            return responses

        # Execute all agents concurrently
        tasks = [process_with_agent(agent) for agent in agents]
        results = await asyncio.gather(*tasks)

        # Flatten results
        all_responses = []
        for result in results:
            all_responses.extend(result)

        self._logger.info(f"Concurrent workflow completed with {len(all_responses)} total responses")
        return all_responses

    async def execute_handoff_workflow(
        self,
        chat_id: str,
        initial_message: str,
        handoff_strategy: Callable[[ChatMessageContent, Optional[Agent]], Optional[Agent]]
    ) -> AsyncIterator[ChatMessageContent]:
        """Execute a handoff workflow where control passes between agents based on conditions."""
        if chat_id not in self._group_chats:
            raise ValueError(f"Group chat with ID {chat_id} not found")

        self._logger.info(f"Starting handoff workflow for chat: {chat_id}")

        chat_history = ChatHistory()
        chat_history.add_user_message(initial_message)

        current_agent = None
        last_response = ChatMessageContent(role=AuthorRole.USER, content=initial_message)

        while True:
            # Determine next agent using handoff strategy
            current_agent = handoff_strategy(last_response, current_agent)
            if current_agent is None:
                break

            self._logger.debug(f"Handing off to agent: {current_agent.name}")

            # Get response from current agent
            async for response in current_agent.invoke(chat_history):
                yield response
                last_response = response

                if response.role == AuthorRole.ASSISTANT:
                    chat_history.add_message(response)

        self._logger.info(f"Handoff workflow completed for chat: {chat_id}")

    def get_agent(self, agent_name: str) -> Optional[Agent]:
        """Get an agent by name."""
        return self._agents.get(agent_name)

    def get_all_agents(self) -> List[Agent]:
        """Get all registered agents."""
        return list(self._agents.values())

    def get_group_chat(self, chat_id: str) -> Optional[AgentGroupChat]:
        """Get a group chat by ID."""
        return self._group_chats.get(chat_id)

    async def execute_group_chat(
        self,
        chat_id: str,
        message: str,
        max_turns: int = 10
    ) -> AsyncIterator[ChatMessageContent]:
        """Execute a group chat conversation."""
        if chat_id not in self._group_chats:
            raise ValueError(f"Group chat with ID {chat_id} not found")

        group_chat = self._group_chats[chat_id]
        self._logger.info(f"Starting group chat conversation: {chat_id}")

        # Add the initial message to chat history
        chat_history = ChatHistory()
        chat_history.add_user_message(message)

        turn_count = 0
        async for response in group_chat.invoke(chat_history):
            yield response

            turn_count += 1
            if turn_count >= max_turns:
                self._logger.info(f"Group chat {chat_id} reached maximum turns ({max_turns})")
                break

        self._logger.info(f"Group chat conversation completed: {chat_id}")

    def _create_default_termination_strategy(self) -> KernelFunction:
        """Create a default termination strategy for group chats."""
        # In Python SK, this might be implemented differently
        # This is a placeholder for the actual implementation
        from semantic_kernel.functions.kernel_function_decorator import kernel_function

        @kernel_function(
            name="ShouldTerminate",
            description="Determines whether a group chat conversation should be terminated"
        )
        def should_terminate(history: str) -> str:
            """
            Determine if the conversation should be terminated based on the chat history.
            Consider the following criteria:
            - Has the main objective been achieved?
            - Are all questions answered satisfactorily?
            - Has the conversation reached a natural conclusion?
            - Is there a clear final decision or recommendation?

            Respond with 'TERMINATE' if the conversation should end, or 'CONTINUE' if it should proceed.
            """
            # Simple heuristic - in production this would be more sophisticated
            if len(history) > 5000 or "conclusion" in history.lower() or "final" in history.lower():
                return "TERMINATE"
            return "CONTINUE"

        return should_terminate


class SimpleHandoffStrategy:
    """Simple handoff strategy based on keywords in responses."""

    def __init__(self, agents: List[Agent], keywords: Dict[str, List[str]]):
        """
        Initialize handoff strategy.

        Args:
            agents: List of available agents
            keywords: Dict mapping agent names to trigger keywords
        """
        self.agents = {agent.name: agent for agent in agents}
        self.keywords = keywords

    def __call__(
        self,
        last_response: ChatMessageContent,
        current_agent: Optional[Agent]
    ) -> Optional[Agent]:
        """Determine next agent based on response content."""
        if not last_response.content:
            return None

        content_lower = last_response.content.lower()

        # Check for handoff keywords
        for agent_name, agent_keywords in self.keywords.items():
            if any(keyword.lower() in content_lower for keyword in agent_keywords):
                return self.agents.get(agent_name)

        # If no handoff keyword found and this is the first call, return first agent
        if current_agent is None and self.agents:
            return next(iter(self.agents.values()))

        # No handoff needed
        return None


class MagneticHandoffStrategy:
    """Advanced handoff strategy that considers agent expertise and context."""

    def __init__(self, agents: List[Agent], expertise_map: Dict[str, List[str]]):
        """
        Initialize magnetic handoff strategy.

        Args:
            agents: List of available agents
            expertise_map: Dict mapping agent names to their areas of expertise
        """
        self.agents = {agent.name: agent for agent in agents}
        self.expertise_map = expertise_map

    def __call__(
        self,
        last_response: ChatMessageContent,
        current_agent: Optional[Agent]
    ) -> Optional[Agent]:
        """Determine next agent based on content analysis and expertise matching."""
        if not last_response.content:
            return None

        content = last_response.content.lower()

        # Score agents based on expertise relevance
        agent_scores = {}
        for agent_name, expertise_areas in self.expertise_map.items():
            score = sum(1 for area in expertise_areas if area.lower() in content)
            agent_scores[agent_name] = score

        # Find the best matching agent
        if agent_scores and max(agent_scores.values()) > 0:
            best_agent_name = max(agent_scores.keys(), key=lambda k: agent_scores[k])
            return self.agents.get(best_agent_name)

        # Default behavior
        return current_agent