"""
Main entry point for the AI Agent Platform with HITL integration.
This serves as the primary executable for the Python implementation.
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from examples.comprehensive_demo import ComprehensiveDemo
from src.observability.telemetry_service import TelemetryService
from src.runtime.runtime_builder import AgentRuntimeBuilder
from src.runtime.runtime_types import AgentRuntime
from src.reasoning.plan_react.process import PlanReactCoordinator
from config import Settings


def setup_logging(log_level: str = "INFO") -> None:
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('agent_platform.log')
        ]
    )


async def run_demo() -> None:
    """Run the comprehensive demonstration."""
    print("🤖 AI Agent Platform with HITL Integration - Python Implementation")
    print("=" * 70)
    print()

    demo = ComprehensiveDemo()
    await demo.run_all_demonstrations_async()


async def run_interactive() -> None:
    """Run an interactive session with the agent platform."""
    print("🤖 Interactive AI Agent Platform Session")
    print("=" * 40)

    settings = Settings()

    if not settings.azure_openai and not settings.openai:
        print("⚠️  Warning: No AI service configured. Heuristic planning will be used.")

    telemetry_service = TelemetryService(settings)
    telemetry_service.initialize()

    async with AgentRuntimeBuilder(settings=settings, telemetry_service=telemetry_service) as runtime:

        print("✅ Agent platform initialized successfully!")
        print()
        print("Available agents:")
        for agent in runtime.agent_orchestrator.get_all_agents():
            print(f"  - {agent.name}")

        print()
        print("Available plugins:")
        plugins = runtime.plugin_manager.get_registered_plugins()
        for plugin_name, plugin_info in plugins.items():
            print(f"  - {plugin_name}: {plugin_info.description}")

        print()
        print("Enter your commands or 'quit' to exit:")

        while True:
            try:
                user_input = input("💬 > ").strip()

                if user_input.lower() in ['quit', 'exit', 'q']:
                    break

                if not user_input:
                    continue

                # Simple command processing
                if user_input.startswith('/'):
                    await process_command(user_input, runtime)
                else:
                    # Process as agent message
                    agents = runtime.agent_orchestrator.get_all_agents()
                    if agents:
                        agent = agents[0]  # Use first available agent
                        # This would be implemented based on SK's Python API
                        print(f"🤖 [{agent.name}]: Processing your request...")
                        print("(Full agent interaction would be implemented here)")
                    else:
                        print("❌ No agents available")

            except KeyboardInterrupt:
                break
            except Exception as ex:
                print(f"❌ Error: {ex}")

        print("\n👋 Goodbye!")

    telemetry_service.shutdown()


async def process_command(command: str, runtime: AgentRuntime) -> None:
    """Process slash commands."""
    cmd = command[1:].lower()

    if cmd == 'help':
        print("Available commands:")
        print("  /help     - Show this help")
        print("  /status   - Show platform status")
        print("  /agents   - List available agents")
        print("  /plugins  - List available plugins")
        print("  /validate - Validate configuration")
        print("  /note <text> - Add pre-run human note for Plan→ReAct")
        print("  /feedback <text> - Record post-run feedback")

    elif cmd == 'status':
        info = _runtime_service_info(runtime)
        print("Platform Status:")
        print(f"  Initialized: {info['initialized']}")
        print(f"  AI Service: {info['ai_service']['type'] if info['ai_service'] else 'None'}")
        print(f"  Agents: {info['agents_count']}")
        print(f"  Plugins: {info['plugins_count']}")

    elif cmd == 'agents':
        agents = runtime.agent_orchestrator.get_all_agents()
        print("Available Agents:")
        for agent in agents:
            print(f"  - {agent.name}: {getattr(agent, 'description', 'No description')}")

    elif cmd == 'plugins':
        plugins = runtime.plugin_manager.get_registered_plugins()
        print("Available Plugins:")
        for plugin_name, plugin_info in plugins.items():
            print(f"  - {plugin_name}: {plugin_info.description}")
            print(f"    Functions: {', '.join(plugin_info.functions)}")

    elif cmd == 'validate':
        print("Validating configuration...")
        validation = await runtime.plugin_manager.validate_plugins_async()
        print(f"✅ Plugins valid: {validation.is_valid}")
        if validation.failed_plugins:
            for name, error in validation.failed_plugins.items():
                print(f"  - {name}: {error}")

    elif cmd.startswith('note'):
        note = command.partition(' ')[2].strip()
        if not note:
            note = input("Enter note: ").strip()
        runtime.context_manager.register_human_note(PlanReactCoordinator.WORKFLOW_ID, 'pre', note)
        runtime.feedback_store.record(
            workflow_id=PlanReactCoordinator.WORKFLOW_ID,
            phase='pre',
            note=note,
            metadata={'source': 'cli'},
        )
        print("Stored pre-run note.")

    elif cmd.startswith('feedback'):
        feedback = command.partition(' ')[2].strip()
        if not feedback:
            feedback = input("Enter feedback: ").strip()
        runtime.context_manager.register_human_note(PlanReactCoordinator.WORKFLOW_ID, 'post', feedback)
        runtime.feedback_store.record(
            workflow_id=PlanReactCoordinator.WORKFLOW_ID,
            phase='post',
            note=feedback,
            metadata={'source': 'cli'},
        )
        print("Recorded feedback.")

    else:
        print(f"❌ Unknown command: {command}")


def _runtime_service_info(runtime: AgentRuntime) -> dict:
    services = getattr(runtime.kernel, "services", {}) or {}
    ai_summary = None

    if services:
        service_id, service = next(iter(services.items()))
        ai_summary = {
            "service_id": service_id,
            "type": type(service).__name__,
        }

        model_name = getattr(service, "deployment_name", None) or getattr(service, "ai_model_id", None)
        if model_name:
            ai_summary["model"] = model_name

        endpoint = getattr(service, "endpoint", None)
        if endpoint:
            ai_summary["endpoint"] = endpoint

    return {
        "initialized": True,
        "ai_service": ai_summary,
        "agents_count": len(runtime.agent_orchestrator.get_all_agents()),
        "plugins_count": len(runtime.plugin_manager.get_registered_plugins()),
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="AI Agent Platform with Human-in-the-Loop Integration"
    )
    parser.add_argument(
        "--mode",
        choices=["demo", "interactive"],
        default="demo",
        help="Run mode (default: demo)"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)

    # Check for .env file
    env_path = Path(__file__).parent / '.env'
    if not env_path.exists():
        print("⚠️  Warning: No .env file found. Please copy .env.example to .env and configure your settings.")
        print()

    # Run the selected mode
    if args.mode == "demo":
        asyncio.run(run_demo())
    elif args.mode == "interactive":
        asyncio.run(run_interactive())


if __name__ == "__main__":
    main()
