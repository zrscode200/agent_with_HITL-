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
from src.services.semantic_kernel_service import SemanticKernelService
from src.observability.telemetry_service import TelemetryService
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

    # Validate configuration
    if not settings.azure_openai and not settings.openai:
        print("❌ Error: No AI service configured.")
        print("Please set either Azure OpenAI or OpenAI credentials in your .env file.")
        print("See .env.example for required environment variables.")
        return

    telemetry_service = TelemetryService(settings)
    telemetry_service.initialize()

    async with SemanticKernelService(settings, telemetry_service=telemetry_service) as sk_service:
        await sk_service.create_default_agents_async()

        print("✅ Agent platform initialized successfully!")
        print()
        print("Available agents:")
        for agent in sk_service.agent_orchestrator.get_all_agents():
            print(f"  - {agent.name}")

        print()
        print("Available plugins:")
        plugins = sk_service.plugin_manager.get_registered_plugins()
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
                    await process_command(user_input, sk_service)
                else:
                    # Process as agent message
                    agents = sk_service.agent_orchestrator.get_all_agents()
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


async def process_command(command: str, sk_service: SemanticKernelService) -> None:
    """Process slash commands."""
    cmd = command[1:].lower()

    if cmd == 'help':
        print("Available commands:")
        print("  /help     - Show this help")
        print("  /status   - Show platform status")
        print("  /agents   - List available agents")
        print("  /plugins  - List available plugins")
        print("  /validate - Validate configuration")

    elif cmd == 'status':
        info = sk_service.get_service_info()
        print("Platform Status:")
        print(f"  Initialized: {info['initialized']}")
        print(f"  AI Service: {info['ai_service']['type'] if info['ai_service'] else 'None'}")
        print(f"  Agents: {info['agents_count']}")
        print(f"  Plugins: {info['plugins_count']}")

    elif cmd == 'agents':
        agents = sk_service.agent_orchestrator.get_all_agents()
        print("Available Agents:")
        for agent in agents:
            print(f"  - {agent.name}: {getattr(agent, 'description', 'No description')}")

    elif cmd == 'plugins':
        plugins = sk_service.plugin_manager.get_registered_plugins()
        print("Available Plugins:")
        for plugin_name, plugin_info in plugins.items():
            print(f"  - {plugin_name}: {plugin_info.description}")
            print(f"    Functions: {', '.join(plugin_info.functions)}")

    elif cmd == 'validate':
        print("Validating configuration...")
        is_valid = await sk_service.validate_configuration_async()
        print(f"✅ Configuration valid: {is_valid}")

    else:
        print(f"❌ Unknown command: {command}")


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