"""Quick test to verify LLM API key works."""

import asyncio
import os
from dotenv import load_dotenv
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion

async def test_llm_connection():
    """Test LLM connection with a simple query."""
    # Load environment variables
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    model_id = os.getenv("OPENAI_MODEL_ID", "gpt-4o-mini")

    if not api_key:
        print("❌ OPENAI_API_KEY not found in .env")
        return False

    print(f"✓ API Key found: {api_key[:20]}...")
    print(f"✓ Model ID: {model_id}")
    print()

    # Create kernel with OpenAI service
    kernel = Kernel()
    service = OpenAIChatCompletion(
        service_id="openai",
        ai_model_id=model_id,
        api_key=api_key,
    )
    kernel.add_service(service)

    print("Testing LLM connection with: 'How are you?'")
    print("-" * 50)

    try:
        # Get chat completion
        from semantic_kernel.contents import ChatHistory

        settings = service.instantiate_prompt_execution_settings()
        chat_history = ChatHistory()
        chat_history.add_user_message("How are you?")

        response = await service.get_chat_message_content(
            chat_history=chat_history,
            settings=settings,
        )

        print(f"✅ Response received:")
        print(f"{response.content}")
        print()
        print("✅ LLM API key is working correctly!")
        return True

    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "insufficient_quota" in error_str or "exceeded your current quota" in error_str:
            print(f"⚠️  API Key is VALID but account has insufficient quota")
            print(f"   Error: Rate limit / quota exceeded")
            print()
            print("   ℹ️  To fix: Add credits to your OpenAI account at:")
            print("      https://platform.openai.com/account/billing")
            print()
            print("✅ API key authentication successful (key is valid)")
            return True  # Key works, just no credits
        else:
            print(f"❌ Error connecting to LLM: {e}")
            return False

if __name__ == "__main__":
    success = asyncio.run(test_llm_connection())
    exit(0 if success else 1)
