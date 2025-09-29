"""Plugin for document processing operations including analysis, validation, and transformation."""

import asyncio
import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from semantic_kernel.functions.kernel_function_decorator import kernel_function

from .base_plugin import BasePlugin
from .tooling_metadata import (
    ApprovalRequirement,
    RiskLevel,
    ToolInput,
    tool_spec,
)


@dataclass
class DocumentAnalysis:
    """Results of document analysis."""
    document_type: str
    word_count: int
    sentence_count: int
    paragraph_count: int
    character_count: int
    analyzed_at: datetime
    language: str
    readability_score: float
    key_topics: List[str]
    has_structured_data: bool


@dataclass
class DocumentValidation:
    """Results of document validation."""
    validation_level: str
    validated_at: datetime
    is_valid: bool
    issues: List[str]
    warnings: List[str]


@dataclass
class InformationExtraction:
    """Results of information extraction."""
    information_type: str
    extracted_at: datetime
    items: List[Any]


@dataclass
class DocumentTransformation:
    """Results of document transformation."""
    source_format: str
    target_format: str
    content: str
    transformed_at: datetime


class DocumentProcessingPlugin(BasePlugin):
    """
    Plugin for document processing operations including analysis, validation, and transformation.
    Python equivalent of the C# DocumentProcessingPlugin with full feature parity.
    """

    @property
    def plugin_name(self) -> str:
        return "DocumentProcessing"

    @property
    def plugin_description(self) -> str:
        return "Plugin for document processing, analysis, and validation operations"

    @tool_spec(
        description="Analyze structured and unstructured documents to surface insights",
        risk_level=RiskLevel.MEDIUM,
        approval=ApprovalRequirement.NONE,
        inputs=[
            ToolInput(name="document_content", description="Full document text to analyze"),
            ToolInput(
                name="document_type",
                description="Optional hint about document type (e.g., contract, policy)",
                required=False,
            ),
        ],
        output_description="JSON payload summarizing key metrics, topics, and language stats",
        tags={"category": "document-analysis"},
    )
    @kernel_function(
        name="analyze_document",
        description="Analyzes document content to extract key information, metadata, and structure"
    )
    async def analyze_document_async(
        self,
        document_content: str,
        document_type: str = "unknown"
    ) -> str:
        """Analyzes document content for approval workflow."""
        function_name = "analyze_document_async"
        self.log_function_start(function_name, {
            "document_content": document_content[:100] + "..." if len(document_content) > 100 else document_content,
            "document_type": document_type
        })

        try:
            self.validate_required_parameter("document_content", document_content)

            analysis = await asyncio.get_event_loop().run_in_executor(
                None, self._perform_document_analysis, document_content, document_type
            )

            result = self.create_success_response(
                function_name,
                analysis.__dict__,
                "Document analysis completed successfully"
            )

            self.log_function_complete(function_name, analysis.__dict__)
            return result

        except Exception as ex:
            self.log_function_error(function_name, ex)
            return self.create_error_response(function_name, "Failed to analyze document", ex)

    @tool_spec(
        description="Validate a document against defined rules and risk thresholds",
        risk_level=RiskLevel.HIGH,
        approval=ApprovalRequirement.POLICY,
        inputs=[
            ToolInput(name="document_content", description="Full document text to validate"),
            ToolInput(
                name="validation_rules",
                description="JSON string describing validation rules",
                required=False,
            ),
            ToolInput(
                name="validation_level",
                description="Validation strictness (e.g., standard, strict)",
                required=False,
            ),
        ],
        output_description="JSON payload detailing validation status, issues, and warnings",
        tags={"category": "document-validation"},
    )
    @kernel_function(
        name="validate_document",
        description="Validates document content against specified criteria and business rules"
    )
    async def validate_document_async(
        self,
        document_content: str,
        validation_rules: str = "{}",
        validation_level: str = "standard"
    ) -> str:
        """Validates document content against specified criteria."""
        function_name = "validate_document_async"
        self.log_function_start(function_name, {
            "document_length": len(document_content) if document_content else 0,
            "validation_rules": validation_rules,
            "validation_level": validation_level
        })

        try:
            self.validate_required_parameter("document_content", document_content)

            validation = await asyncio.get_event_loop().run_in_executor(
                None, self._perform_document_validation, document_content, validation_rules, validation_level
            )

            result = self.create_success_response(
                function_name,
                validation.__dict__,
                "Document validation completed"
            )

            self.log_function_complete(function_name, validation.__dict__)
            return result

        except Exception as ex:
            self.log_function_error(function_name, ex)
            return self.create_error_response(function_name, "Failed to validate document", ex)

    @tool_spec(
        description="Extract targeted entities (dates, parties, etc.) from a document",
        risk_level=RiskLevel.MEDIUM,
        approval=ApprovalRequirement.NONE,
        inputs=[
            ToolInput(name="document_content", description="Full document text"),
            ToolInput(name="information_type", description="Type of information to extract"),
            ToolInput(
                name="custom_pattern",
                description="Optional custom regex or pattern",
                required=False,
            ),
        ],
        output_description="JSON payload listing extracted items with metadata",
        tags={"category": "document-extraction"},
    )
    @kernel_function(
        name="extract_information",
        description="Extracts specific information from document content using patterns, keywords, or regex"
    )
    async def extract_information_async(
        self,
        document_content: str,
        information_type: str,
        custom_pattern: Optional[str] = None
    ) -> str:
        """Extracts specific information from document content using patterns or keywords."""
        function_name = "extract_information_async"
        self.log_function_start(function_name, {
            "document_length": len(document_content) if document_content else 0,
            "information_type": information_type,
            "custom_pattern": custom_pattern
        })

        try:
            self.validate_required_parameter("document_content", document_content)
            self.validate_required_parameter("information_type", information_type)

            extracted_info = await asyncio.get_event_loop().run_in_executor(
                None, self._extract_specific_information, document_content, information_type, custom_pattern
            )

            result = self.create_success_response(
                function_name,
                extracted_info.__dict__,
                f"Information extraction completed for type: {information_type}"
            )

            self.log_function_complete(function_name, extracted_info.__dict__)
            return result

        except Exception as ex:
            self.log_function_error(function_name, ex)
            return self.create_error_response(function_name, "Failed to extract information", ex)

    @tool_spec(
        description="Transform a document into another format such as summary or outline",
        risk_level=RiskLevel.MEDIUM,
        approval=ApprovalRequirement.NONE,
        inputs=[
            ToolInput(name="document_content", description="Full document text to transform"),
            ToolInput(name="target_format", description="Output format (summary, outline, etc.)"),
            ToolInput(
                name="options",
                description="JSON string with transformation options",
                required=False,
            ),
        ],
        output_description="JSON payload containing the transformed content",
        tags={"category": "document-transformation"},
    )
    @kernel_function(
        name="transform_document",
        description="Transforms document content to different formats (summary, outline, structured_data, etc.)"
    )
    async def transform_document_async(
        self,
        document_content: str,
        target_format: str,
        options: str = "{}"
    ) -> str:
        """Transforms document content to a different format or structure."""
        function_name = "transform_document_async"
        self.log_function_start(function_name, {
            "document_length": len(document_content) if document_content else 0,
            "target_format": target_format,
            "options": options
        })

        try:
            self.validate_required_parameter("document_content", document_content)
            self.validate_required_parameter("target_format", target_format)

            transformed = await asyncio.get_event_loop().run_in_executor(
                None, self._transform_document_content, document_content, target_format, options
            )

            result = self.create_success_response(
                function_name,
                transformed.__dict__,
                f"Document transformed to {target_format}"
            )

            self.log_function_complete(function_name, transformed.__dict__)
            return result

        except Exception as ex:
            self.log_function_error(function_name, ex)
            return self.create_error_response(function_name, "Failed to transform document", ex)

    def _perform_document_analysis(self, content: str, document_type: str) -> DocumentAnalysis:
        """Perform document analysis synchronously."""
        words = content.split()
        sentences = [s.strip() for s in re.split(r'[.!?]+', content) if s.strip()]
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', content) if p.strip()]

        return DocumentAnalysis(
            document_type=document_type,
            word_count=len(words),
            sentence_count=len(sentences),
            paragraph_count=len(paragraphs),
            character_count=len(content),
            analyzed_at=datetime.utcnow(),
            language=self._detect_language(content),
            readability_score=self._calculate_readability_score(len(words), len(sentences)),
            key_topics=self._extract_key_topics(words),
            has_structured_data=self._detect_structured_data(content)
        )

    def _perform_document_validation(self, content: str, rules_json: str, level: str) -> DocumentValidation:
        """Perform document validation synchronously."""
        validation = DocumentValidation(
            validation_level=level,
            validated_at=datetime.utcnow(),
            is_valid=True,
            issues=[],
            warnings=[]
        )

        # Basic validation
        if not content.strip():
            validation.issues.append("Document content is empty")
            validation.is_valid = False

        # Length validation based on level
        min_length = {
            "basic": 10,
            "standard": 50,
            "strict": 100
        }.get(level, 50)

        if len(content) < min_length:
            validation.issues.append(f"Document too short for {level} validation (minimum {min_length} characters)")
            validation.is_valid = False

        # Additional validations for higher levels
        if level in ["standard", "strict"]:
            sentences = [s.strip() for s in re.split(r'[.!?]+', content) if s.strip()]
            if len(sentences) < 2:
                validation.warnings.append("Document contains very few sentences")

        if level == "strict":
            if not any(c in content for c in '.!?'):
                validation.warnings.append("Document lacks proper punctuation")

        return validation

    def _extract_specific_information(
        self,
        content: str,
        info_type: str,
        custom_pattern: Optional[str]
    ) -> InformationExtraction:
        """Extract specific information synchronously."""
        extraction = InformationExtraction(
            information_type=info_type,
            extracted_at=datetime.utcnow(),
            items=[]
        )

        info_type_lower = info_type.lower()

        if info_type_lower == "emails":
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            extraction.items = re.findall(email_pattern, content)

        elif info_type_lower == "phone_numbers":
            phone_pattern = r'(\+\d{1,3}[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}'
            extraction.items = re.findall(phone_pattern, content)

        elif info_type_lower == "dates":
            date_pattern = r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b'
            extraction.items = re.findall(date_pattern, content)

        elif info_type_lower == "custom" and custom_pattern:
            try:
                extraction.items = re.findall(custom_pattern, content)
            except re.error as e:
                self._logger.warning(f"Invalid regex pattern: {custom_pattern}, error: {e}")
                extraction.items = []

        return extraction

    def _transform_document_content(self, content: str, target_format: str, options_json: str) -> DocumentTransformation:
        """Transform document content synchronously."""
        transformation = DocumentTransformation(
            source_format="text",
            target_format=target_format,
            content="",
            transformed_at=datetime.utcnow()
        )

        target_format_lower = target_format.lower()

        if target_format_lower == "summary":
            sentences = [s.strip() for s in re.split(r'[.!?]+', content) if s.strip()]
            transformation.content = '. '.join(sentences[:min(3, len(sentences))]) + '.'

        elif target_format_lower == "outline":
            paragraphs = [p.strip() for p in re.split(r'\n\s*\n', content) if p.strip()]
            lines = []
            for i, paragraph in enumerate(paragraphs):
                first_sentence = paragraph.split('.')[0] if '.' in paragraph else paragraph[:50]
                lines.append(f"{i + 1}. {first_sentence}...")
            transformation.content = '\n'.join(lines)

        elif target_format_lower == "bullet_points":
            sentences = [s.strip() for s in re.split(r'[.\n]+', content) if s.strip()]
            points = [f"• {s.strip()}" for s in sentences[:10] if s.strip()]
            transformation.content = '\n'.join(points)

        else:
            transformation.content = content  # No transformation

        return transformation

    def _detect_language(self, content: str) -> str:
        """Simple language detection."""
        common_english_words = ["the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"]
        word_count = sum(1 for word in common_english_words if word in content.lower())
        return "English" if word_count > 5 else "Unknown"

    def _calculate_readability_score(self, word_count: int, sentence_count: int) -> float:
        """Calculate a simple readability score."""
        if sentence_count == 0:
            return 0.0
        avg_words_per_sentence = word_count / sentence_count
        return max(0.0, min(100.0, 100 - (avg_words_per_sentence * 2)))

    def _extract_key_topics(self, words: List[str]) -> List[str]:
        """Extract key topics from words."""
        # Filter out common words and short words
        filtered_words = [
            word.lower() for word in words
            if len(word) > 4 and not self._is_common_word(word)
        ]

        # Count word frequency
        word_counts = {}
        for word in filtered_words:
            word_counts[word] = word_counts.get(word, 0) + 1

        # Return top 5 most frequent words
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        return [word for word, count in sorted_words[:5]]

    def _is_common_word(self, word: str) -> bool:
        """Check if a word is a common word that should be filtered out."""
        common_words = {
            "that", "this", "with", "have", "will", "been", "they", "their",
            "there", "where", "when", "what", "which", "would", "could", "should"
        }
        return word.lower() in common_words

    def _detect_structured_data(self, content: str) -> bool:
        """Detect if content contains structured data."""
        structured_indicators = ["JSON", "XML", "CSV", "{", "}", "<", ">", ","]
        return any(indicator in content for indicator in structured_indicators) or \
               bool(re.search(r'^\s*\{.*\}\s*$', content, re.MULTILINE))
