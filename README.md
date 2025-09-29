# AI Agent Platform with Human-in-the-Loop Integration

A comprehensive AI agent platform built on Microsoft's Semantic Kernel with integrated Human-in-the-Loop workflows, custom tools, and enterprise-grade observability.

**🐍 Pure Python Implementation** - A production-ready Python platform for AI agents with sophisticated HITL workflows and enterprise observability.

## Features

- **Multi-Agent Orchestration**: Built on Semantic Kernel's GA Agent Framework with support for concurrent, sequential, handoff, and group chat patterns
- **Human-in-the-Loop Integration**: Native HITL workflows using SK's Process Framework with approval gates and interruption capabilities
- **Custom Tool System**: Extensible plugin architecture using SK's native KernelFunction system and MCP protocol support
- **Enterprise Observability**: Built-in OpenTelemetry compliance with custom metrics, distributed tracing, and structured logging
- **Security Filters**: Comprehensive input validation, malicious content detection, and access control
- **Interoperability**: Support for Agent-to-Agent (A2A) protocol and Model Context Protocol (MCP)

## Architecture

```
agent-platform/
├── src/
│   ├── agents/               # SK Agent Framework implementations
│   ├── plugins/              # Custom tools and MCP connectors
│   ├── filters/              # Security and telemetry filters
│   ├── services/             # Core platform services
│   └── observability/        # OpenTelemetry integration
├── examples/                 # Comprehensive demos
├── tests/                    # Unit tests (coming soon)
├── config.py                 # Configuration management
├── main.py                   # Main entry point
├── requirements.txt          # Python dependencies
└── monitoring/               # Observability dashboards
```

## Technology Stack

- **Semantic Kernel v1.37.0** (latest Python release as of Sept 2025)
- **SK Agent Framework (GA)** - Production-ready multi-agent orchestration
- **OpenTelemetry** - Native observability and monitoring
- **HTTPX** - Modern async HTTP client
- **Pydantic** - Data validation and settings management
- **AsyncIO** - Native async/await support throughout

## Quick Start

### Prerequisites

- Python 3.11+
- Azure OpenAI or OpenAI API access
- (Optional) Azure Monitor for observability

### Installation

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API credentials
```

### Configuration

Edit `.env` file with your credentials:

```bash
# Azure OpenAI (recommended)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-azure-openai-api-key
AZURE_OPENAI_MODEL_ID=gpt-4-turbo

# Or OpenAI
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL_ID=gpt-4-turbo
```

### Run the Demo

```bash
# Run comprehensive demo
python main.py --mode demo

# Run interactive mode
python main.py --mode interactive

# Run with debug logging
python main.py --mode demo --log-level DEBUG
```

## Usage Examples

### Basic Agent Setup

```python
import asyncio
from src.services.semantic_kernel_service import SemanticKernelService
from config import Settings

async def main():
    settings = Settings()

    async with SemanticKernelService(settings) as service:
        await service.create_default_agents_async()

        # Get an agent
        orchestrator = service.agent_orchestrator
        agent = orchestrator.get_agent("DocumentAnalyst")

        # Use the agent
        if agent:
            async for response in agent.invoke("Analyze this document..."):
                print(response)

asyncio.run(main())
```

### Custom Plugin Development

```python
from src.plugins.base_plugin import BasePlugin
from semantic_kernel.functions.kernel_function_decorator import kernel_function

class MyCustomPlugin(BasePlugin):
    @property
    def plugin_name(self) -> str:
        return "MyPlugin"

    @property
    def plugin_description(self) -> str:
        return "My custom plugin for specialized tasks"

    @kernel_function(
        name="process_data",
        description="Process data with custom logic"
    )
    async def process_data_async(self, data: str, format: str = "json") -> str:
        # Your custom processing logic here
        return self.create_success_response("process_data", {"processed": True})
```

### HITL Workflow Example

```python
# The platform automatically handles HITL workflows
# based on risk assessment and approval requirements

documents = [
    {"title": "Contract", "content": "CONFIDENTIAL agreement..."},
    {"title": "Policy", "content": "Standard policy document..."}
]

for doc in documents:
    # Risk is automatically assessed
    # High-risk documents trigger human approval
    # Low-risk documents auto-approve
    result = await process_document_with_hitl(doc)
    print(f"Document {doc['title']}: {result.status}")
```

### Multi-Agent Orchestration

```python
# Sequential workflow
agents = [document_analyst, approval_coordinator]
async for response in orchestrator.execute_sequential_workflow(
    agents, "Analyze this contract for risks"
):
    print(f"[{response.author_name}]: {response.content}")

# Concurrent workflow
responses = await orchestrator.execute_concurrent_workflow(
    agents, "Provide different perspectives on this document"
)
```

## Key Implementation Highlights

### 🏗️ **Enterprise-Grade Architecture**
- Production-ready Python implementation with sophisticated design patterns
- Comprehensive error handling and structured logging
- Modern async/await patterns throughout

### 🔧 **Advanced Plugin System**
- `BasePlugin` class for standardized plugin development
- Automatic function registration with SK's kernel
- Built-in security validation and telemetry collection
- Support for async operations and complex data types

### 🛡️ **Enterprise Security**
- `SecurityFilter` for input validation and malicious content detection
- Protection against injection attacks, path traversal, and unsafe operations
- Configurable security policies and restricted function lists

### 📊 **Production-Ready Observability**
- OpenTelemetry integration with multiple exporters (Console, OTLP, Azure Monitor)
- Custom metrics for agent performance, token usage, and approval latency
- Distributed tracing across agent interactions
- Health checks and configuration validation

### 🔄 **Sophisticated HITL Workflows**
- Automatic risk assessment and escalation
- Multiple notification channels (console, email, webhooks)
- Configurable approval timeouts and policies
- Audit trails for all human decisions

### 🚀 **Modern Python Practices**
- Full type hints and Pydantic models
- Async/await throughout the codebase
- Context managers for resource management
- Comprehensive error handling and logging

## Development

### Running Tests

```bash
pytest tests/ -v --cov=src --cov-report=html
```

### Code Quality

```bash
# Format code
black src/ examples/ tests/

# Sort imports
isort src/ examples/ tests/

# Lint
flake8 src/ examples/ tests/

# Type checking
mypy src/
```

## Monitoring & Observability

The platform includes comprehensive observability features:

- **Metrics**: Agent execution times, token usage, error rates, approval latency
- **Tracing**: Distributed tracing across agent interactions and plugin calls
- **Logging**: Structured logging with correlation IDs
- **Health Checks**: Automatic validation of configuration and plugin status

### Sample Metrics Collected

- `agent_executions_total` - Counter of agent executions
- `agent_execution_duration_seconds` - Histogram of execution times
- `token_usage_total` - Counter of tokens consumed by AI models
- `approval_latency_seconds` - Histogram of human approval response times
- `errors_total` - Counter of errors by component and type

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes to the codebase
4. Add tests for new functionality
5. Run the test suite and ensure all tests pass
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## Roadmap

- [ ] Web UI for agent management and HITL approvals
- [ ] Additional plugin templates and examples
- [ ] Integration with popular workflow engines
- [ ] Enhanced security policies and RBAC
- [ ] Performance optimization and caching
- [ ] Multi-language support for agents

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Documentation**: See the `/docs` directory for detailed documentation
- **Examples**: Check the `/examples` directory for comprehensive examples
- **Issues**: Report bugs and request features via GitHub Issues
- **Discussions**: Join the community discussion for questions and ideas

---

**Built with ❤️ using Microsoft Semantic Kernel and modern Python practices**