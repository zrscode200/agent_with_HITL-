"""
Comprehensive demonstration of the AI Agent Platform with HITL integration in Python.
This is the Python equivalent of the C# DocumentProcessingExample with full feature parity.
"""

import asyncio
import logging
import sys
import json
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import httpx

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.semantic_kernel_service import SemanticKernelService
from src.observability.telemetry_service import TelemetryService
from config import Settings


@dataclass
class SampleDocument:
    """Sample document for demonstration."""
    id: str
    title: str
    type: str
    content: str


@dataclass
class ApprovalRequest:
    """Approval request data model."""
    id: str
    risk_level: str
    risk_factors: List[str]
    requested_at: datetime
    status: str


@dataclass
class ApprovalDecision:
    """Approval decision data model."""
    approval_id: str
    is_approved: bool
    comments: str
    approver_name: str
    decided_at: datetime


class ComprehensiveDemo:
    """
    Comprehensive demonstration class for the AI Agent Platform.
    Python equivalent of the C# DocumentProcessingExample with full feature parity.
    """

    def __init__(self):
        """Initialize the demonstration."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.settings = Settings()
        self.semantic_kernel_service: Optional[SemanticKernelService] = None
        self.telemetry_service: Optional[TelemetryService] = None
        self.http_client: Optional[httpx.AsyncClient] = None

    async def run_all_demonstrations_async(self) -> None:
        """Run all demonstration examples."""
        self.logger.info("Starting AI Agent Platform comprehensive demonstration")

        try:
            # Initialize services
            await self._initialize_services_async()

            print("=== AI Agent Platform with HITL Integration Demo ===\n")

            # Run plugin demonstration
            await self.run_plugin_demonstration_async()
            print("\n" + "=" * 60 + "\n")

            # Run HTTP plugin demonstration
            await self.run_http_plugin_demonstration_async()
            print("\n" + "=" * 60 + "\n")

            # Run multi-agent document analysis
            await self.run_multi_agent_document_analysis_async()
            print("\n" + "=" * 60 + "\n")

            # Run document processing workflow with HITL
            await self.run_document_processing_workflow_async()
            print("\n" + "=" * 60 + "\n")

            # Run observability demonstration
            await self.run_observability_demo_async()

            print("\nDemo completed successfully!")

        except Exception as ex:
            self.logger.error(f"Error during demo execution: {ex}", exc_info=ex)
            raise

        finally:
            await self._cleanup_async()

    async def run_plugin_demonstration_async(self) -> None:
        """Demonstrate plugin usage for document processing tasks."""
        self.logger.info("Starting plugin demonstration example")

        try:
            kernel = self.semantic_kernel_service.kernel
            plugin_manager = self.semantic_kernel_service.plugin_manager
            sample_document = self._create_sample_documents()[1]  # Use the contract document

            print("=== Plugin Demonstration ===")
            print(f"Processing document: {sample_document.title}\n")

            # 1. Document Analysis Plugin
            self.logger.info("Demonstrating DocumentProcessing plugin")

            # Get the plugin
            doc_plugin = plugin_manager.get_plugin("DocumentProcessing")
            if doc_plugin:
                analysis_result = await doc_plugin.analyze_document_async(
                    document_content=sample_document.content,
                    document_type="contract"
                )

                print("Document Analysis Result:")
                self._print_json_response(analysis_result)

                # 2. Document Validation
                validation_result = await doc_plugin.validate_document_async(
                    document_content=sample_document.content,
                    validation_rules="{}",
                    validation_level="strict"
                )

                print("\nDocument Validation Result:")
                self._print_json_response(validation_result)

                # 3. Information Extraction
                extraction_result = await doc_plugin.extract_information_async(
                    document_content=sample_document.content,
                    information_type="dates"
                )

                print("\nInformation Extraction Result:")
                self._print_json_response(extraction_result)

                # 4. Document Transformation
                transform_result = await doc_plugin.transform_document_async(
                    document_content=sample_document.content,
                    target_format="summary"
                )

                print("\nDocument Transformation Result:")
                self._print_json_response(transform_result)

            self.logger.info("Plugin demonstration completed successfully")

        except Exception as ex:
            self.logger.error("Error during plugin demonstration", exc_info=ex)
            raise

    async def run_http_plugin_demonstration_async(self) -> None:
        """Demonstrate HTTP plugin usage for external data integration."""
        self.logger.info("Starting HTTP plugin demonstration")

        try:
            plugin_manager = self.semantic_kernel_service.plugin_manager

            print("=== HTTP Plugin Demonstration ===")

            # Get the HTTP plugin
            http_plugin = plugin_manager.get_plugin("HttpWeb")
            if http_plugin:
                # 1. Check URL Status
                status_result = await http_plugin.check_url_status_async(
                    url="https://httpbin.org/status/200"
                )

                print("URL Status Check Result:")
                self._print_json_response(status_result)

                # 2. Fetch JSON Data (using a public API)
                json_result = await http_plugin.fetch_json_data_async(
                    api_url="https://httpbin.org/json"
                )

                print("\nJSON Data Fetch Result:")
                self._print_json_response(json_result)

                # 3. HTTP GET Request
                get_result = await http_plugin.http_get_async(
                    url="https://httpbin.org/get?demo=true"
                )

                print("\nHTTP GET Result:")
                self._print_json_response(get_result)

            self.logger.info("HTTP plugin demonstration completed successfully")

        except Exception as ex:
            self.logger.error("Error during HTTP plugin demonstration", exc_info=ex)
            raise

    async def run_multi_agent_document_analysis_async(self) -> None:
        """Demonstrate multi-agent collaboration for document analysis."""
        self.logger.info("Starting multi-agent document analysis example")

        sample_document = self._create_sample_documents()[0]

        try:
            print("=== Multi-Agent Document Analysis ===")
            print(f"Analyzing document: {sample_document.title}\n")

            # Get agents from the orchestrator
            orchestrator = self.semantic_kernel_service.agent_orchestrator
            all_agents = orchestrator.get_all_agents()

            if len(all_agents) >= 2:
                agents = all_agents[:2]  # Use first 2 agents

                # 1. Sequential workflow - Analyst then Coordinator
                print("Sequential Analysis Workflow:")
                message = (f"Please analyze this document and provide recommendations:\n\n"
                          f"Title: {sample_document.title}\nContent: {sample_document.content}")

                async for response in orchestrator.execute_sequential_workflow(agents, message):
                    if hasattr(response, 'author_name') and hasattr(response, 'content'):
                        print(f"[{response.author_name}]: {response.content}")
                    else:
                        print(f"[Agent]: {response}")

                # 2. Concurrent workflow - Multiple perspectives
                print("\nConcurrent Analysis Workflow:")
                concurrent_message = (f"Provide your perspective on this document:\n\n"
                                    f"Title: {sample_document.title}\nContent: {sample_document.content}")

                concurrent_responses = await orchestrator.execute_concurrent_workflow(agents, concurrent_message)

                for response in concurrent_responses:
                    if hasattr(response, 'author_name') and hasattr(response, 'content'):
                        print(f"[Concurrent - {response.author_name}]: {response.content}")
                    else:
                        print(f"[Concurrent Agent]: {response}")

            else:
                print("Not enough agents available for multi-agent demonstration")

            self.logger.info("Multi-agent document analysis completed")

        except Exception as ex:
            self.logger.error("Error during multi-agent document analysis", exc_info=ex)
            raise

    async def run_document_processing_workflow_async(self) -> None:
        """Demonstrate a complete document processing workflow with HITL integration."""
        self.logger.info("Starting document processing workflow example")

        try:
            print("=== Document Processing Workflow with HITL ===")

            # Create sample documents for processing
            documents = self._create_sample_documents()

            # Process each document through the workflow
            for document in documents:
                self.logger.info(f"Processing document: {document.title}")
                await self._process_single_document_async(document)

            self.logger.info("Document processing workflow example completed successfully")

        except Exception as ex:
            self.logger.error("Error during document processing workflow example", exc_info=ex)
            raise

    async def run_observability_demo_async(self) -> None:
        """Demonstrate observability features."""
        self.logger.info("Starting observability demonstration")

        print("=== Observability and Monitoring ===")

        try:
            if self.telemetry_service:
                # Record some sample metrics
                self.telemetry_service.record_agent_execution("DemoAgent", 1.5, True, {"demo": "true"})
                self.telemetry_service.record_token_usage("gpt-4", "demo_operation", 100, 50, 150)
                self.telemetry_service.record_approval_latency("document", 30.0, True, "medium")

                print("Sample telemetry data recorded:")
                print("- Agent execution: DemoAgent (1.5s, success)")
                print("- Token usage: 100 prompt + 50 completion = 150 total")
                print("- Approval latency: 30s (approved, medium risk)")

            # Show service information
            service_info = self.semantic_kernel_service.get_service_info()
            print(f"\nService Information:")
            self._print_json_data(service_info)

            # Validate plugin status
            plugin_manager = self.semantic_kernel_service.plugin_manager
            validation_result = await plugin_manager.validate_plugins_async()

            print(f"\nPlugin Validation:")
            print(f"- Total plugins: {validation_result.total_plugins}")
            print(f"- Successful: {len(validation_result.successful_plugins)}")
            print(f"- Failed: {len(validation_result.failed_plugins)}")
            print(f"- Is valid: {validation_result.is_valid}")

            self.logger.info("Observability demonstration completed")

        except Exception as ex:
            self.logger.error("Error during observability demonstration", exc_info=ex)
            raise

    # Private helper methods

    async def _initialize_services_async(self) -> None:
        """Initialize all required services."""
        self.logger.info("Initializing services for demonstration")

        # Initialize HTTP client
        self.http_client = httpx.AsyncClient(timeout=30.0)

        # Initialize telemetry service
        self.telemetry_service = TelemetryService(self.settings, self.logger)
        self.telemetry_service.initialize()

        # Initialize semantic kernel service
        self.semantic_kernel_service = SemanticKernelService(
            settings=self.settings,
            logger=self.logger,
            telemetry_service=self.telemetry_service
        )

        await self.semantic_kernel_service.initialize_async(self.http_client)
        await self.semantic_kernel_service.create_default_agents_async()

    async def _cleanup_async(self) -> None:
        """Cleanup resources."""
        if self.http_client:
            await self.http_client.aclose()

        if self.telemetry_service:
            self.telemetry_service.shutdown()

    async def _process_single_document_async(self, document: SampleDocument) -> None:
        """Process a single document through the HITL workflow."""
        try:
            print(f"\nProcessing Document: {document.title}")
            print("-" * 50)

            await self._simulate_process_execution_async(document)

        except Exception as ex:
            self.logger.error(f"Error processing document: {document.title}", exc_info=ex)
            raise

    async def _simulate_process_execution_async(self, document: SampleDocument) -> None:
        """Simulate the HITL process execution."""
        print("Step 1: Analyzing document content")
        await asyncio.sleep(0.5)  # Simulate analysis time

        print("Step 2: Assessing risk level")
        risk_level = self._determine_document_risk(document)
        await asyncio.sleep(0.3)

        if risk_level in ["HIGH", "MEDIUM"]:
            print(f"Step 3: Requesting human approval (Risk Level: {risk_level})")

            # Simulate approval request
            approval_request = ApprovalRequest(
                id=f"approval_{document.id}",
                risk_level=risk_level,
                risk_factors=self._get_risk_factors(document),
                requested_at=datetime.utcnow(),
                status="PENDING"
            )

            print(f"\n*** APPROVAL REQUIRED ***")
            print(f"Document: {document.title}")
            print(f"Risk Level: {risk_level}")
            print(f"Risk Factors: {', '.join(approval_request.risk_factors)}")
            print("Simulating human approval...")

            # Simulate human approval with delay
            approval_decision = await self._simulate_human_approval_async(approval_request.id)

            if approval_decision.is_approved:
                self.logger.info(f"Document approved: {approval_decision.approval_id}")
                await self._final_processing_async(document, True)
            else:
                self.logger.warning(f"Document rejected: {approval_decision.approval_id}")
                await self._final_processing_async(document, False)

            # Record approval latency
            if self.telemetry_service:
                latency = (approval_decision.decided_at - approval_request.requested_at).total_seconds()
                self.telemetry_service.record_approval_latency(
                    "document", latency, approval_decision.is_approved, risk_level.lower()
                )

        else:
            print("Step 3: Auto-approving low-risk document")
            await self._final_processing_async(document, True)

    async def _simulate_human_approval_async(self, approval_id: str) -> ApprovalDecision:
        """Simulate human approval decision."""
        # Simulate processing time
        await asyncio.sleep(1)

        # For demo purposes, approve medium risk documents, reject high risk
        is_approved = True  # In demo, we'll approve most requests

        return ApprovalDecision(
            approval_id=approval_id,
            is_approved=is_approved,
            comments="Approved for demo purposes" if is_approved else "High risk document rejected",
            approver_name="Demo User",
            decided_at=datetime.utcnow()
        )

    async def _final_processing_async(self, document: SampleDocument, approved: bool) -> None:
        """Simulate final document processing."""
        if approved:
            print("Step 4: Final processing - Document approved and processed")
        else:
            print("Step 4: Final processing - Document rejected, no further action")

        await asyncio.sleep(0.3)  # Simulate processing time
        print(f"Document processing completed for: {document.title}")

    def _determine_document_risk(self, document: SampleDocument) -> str:
        """Determine document risk level."""
        content_lower = document.content.lower()

        if document.type == "contract" or "confidential" in content_lower:
            return "HIGH"
        elif "financial" in content_lower or len(document.content) > 2000:
            return "MEDIUM"
        else:
            return "LOW"

    def _get_risk_factors(self, document: SampleDocument) -> List[str]:
        """Get risk factors for a document."""
        factors = []
        content_lower = document.content.lower()

        if document.type == "contract":
            factors.append("Legal contract document")
        if "confidential" in content_lower:
            factors.append("Contains confidential information")
        if "financial" in content_lower:
            factors.append("Contains financial information")
        if len(document.content) > 2000:
            factors.append("Large document size")

        return factors or ["Standard document"]

    def _create_sample_documents(self) -> List[SampleDocument]:
        """Create sample documents for demonstration."""
        return [
            SampleDocument(
                id="doc_1",
                title="Employee Handbook Update",
                type="policy",
                content="This document outlines the updated employee handbook policies effective January 2025. "
                       "Key changes include remote work policies, updated benefits information, and new compliance requirements. "
                       "All employees are required to review and acknowledge these changes by the end of the month."
            ),
            SampleDocument(
                id="doc_2",
                title="Software License Agreement",
                type="contract",
                content="CONFIDENTIAL SOFTWARE LICENSE AGREEMENT\n"
                       "This agreement governs the use of proprietary software systems. The licensee agrees to pay "
                       "a licensing fee of $50,000 annually, with payment due on 2025-03-15. This software contains "
                       "trade secrets and proprietary algorithms that must be protected. Violation of this agreement "
                       "may result in legal action and financial penalties up to $100,000."
            ),
            SampleDocument(
                id="doc_3",
                title="Meeting Minutes - Weekly Standup",
                type="minutes",
                content="Weekly team standup meeting held on 2025-01-15.\n"
                       "Attendees: John, Sarah, Mike, Lisa\n"
                       "Topics discussed: Sprint progress, upcoming deadlines, resource allocation.\n"
                       "Action items: Complete code review by Friday, schedule client demo for next week."
            )
        ]

    def _print_json_response(self, response: str) -> None:
        """Pretty print a JSON response."""
        try:
            data = json.loads(response)
            print(json.dumps(data, indent=2))
        except json.JSONDecodeError:
            print(response)

    def _print_json_data(self, data: Any) -> None:
        """Pretty print JSON data."""
        print(json.dumps(data, indent=2, default=str))


async def main():
    """Main entry point for the comprehensive demonstration."""
    demo = ComprehensiveDemo()
    await demo.run_all_demonstrations_async()


if __name__ == "__main__":
    asyncio.run(main())