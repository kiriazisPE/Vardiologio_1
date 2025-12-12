# -*- coding: utf-8 -*-
"""
DSPy Configuration for Shift Scheduling
Sets up DSPy with OpenAI as the LLM backend.
"""

import os
import dspy
from openai import OpenAI
from dotenv import load_dotenv
from typing import Optional

# Load environment variables
load_dotenv()

# Global variables
_dspy_configured = False
_llm = None
_client = None


def get_openai_api_key() -> Optional[str]:
    """
    Get OpenAI API key from environment.
    
    Returns:
        API key or None if not found
    """
    # Try different environment variable names
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OpenAI_API_KEY")
    
    if api_key:
        # Remove quotes if present
        api_key = api_key.strip("'\"")
    
    return api_key


def configure_dspy(
    model: str = "gpt-4o-mini",
    max_tokens: int = 4000,
    temperature: float = 0.2,
    api_key: Optional[str] = None,
    force_reconfigure: bool = False
) -> bool:
    """
    Configure DSPy with OpenAI as the LLM backend.
    
    Args:
        model: OpenAI model name (default: gpt-4o-mini)
        max_tokens: Maximum tokens per response (default: 4000)
        temperature: Sampling temperature (default: 0.2 for deterministic scheduling)
        api_key: OpenAI API key (uses env var if not provided)
        force_reconfigure: Force reconfiguration even if already configured
    
    Returns:
        True if configuration successful, False otherwise
    """
    global _dspy_configured, _llm, _client
    
    # Check if already configured
    if _dspy_configured and not force_reconfigure:
        return True
    
    # Get API key
    if api_key is None:
        api_key = get_openai_api_key()
    
    if not api_key:
        print("❌ OpenAI API key not found!")
        print("   Set OPENAI_API_KEY environment variable or pass api_key parameter.")
        return False
    
    try:
        # Create OpenAI client
        _client = OpenAI(api_key=api_key)
        
        # Test the client with a simple call
        try:
            _client.models.list()
        except Exception as e:
            print(f"❌ Failed to connect to OpenAI: {e}")
            return False
        
        # Configure DSPy with OpenAI (DSPy 3.0+ API)
        try:
            # Try new DSPy 3.0+ API
            _llm = dspy.LM(
                model=f"openai/{model}",
                api_key=api_key,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except (AttributeError, TypeError):
            # Fallback for older DSPy versions
            try:
                _llm = dspy.OpenAI(
                    model=model,
                    api_key=api_key,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            except AttributeError:
                print(f"❌ Unable to initialize DSPy LM. Please check DSPy version.")
                return False
        
        dspy.settings.configure(lm=_llm)
        
        _dspy_configured = True
        
        print(f"✅ DSPy configured successfully!")
        print(f"   Model: {model}")
        print(f"   Max tokens: {max_tokens}")
        print(f"   Temperature: {temperature}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to configure DSPy: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_dspy_llm():
    """
    Get the configured DSPy LLM instance.
    
    Returns:
        DSPy LLM instance or None if not configured
    """
    if not _dspy_configured:
        configure_dspy()
    
    return _llm


def get_openai_client() -> Optional[OpenAI]:
    """
    Get the OpenAI client instance.
    
    Returns:
        OpenAI client or None if not configured
    """
    if not _client:
        configure_dspy()
    
    return _client


def is_configured() -> bool:
    """
    Check if DSPy is configured.
    
    Returns:
        True if configured, False otherwise
    """
    return _dspy_configured


def reconfigure(
    model: str = "gpt-4o-mini",
    max_tokens: int = 4000,
    temperature: float = 0.2,
    api_key: Optional[str] = None
) -> bool:
    """
    Reconfigure DSPy with new settings.
    
    Args:
        model: OpenAI model name
        max_tokens: Maximum tokens per response
        temperature: Sampling temperature
        api_key: OpenAI API key
    
    Returns:
        True if reconfiguration successful, False otherwise
    """
    return configure_dspy(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        api_key=api_key,
        force_reconfigure=True
    )


# Auto-configure on import
def auto_configure():
    """
    Automatically configure DSPy on module import if API key is available.
    """
    api_key = get_openai_api_key()
    if api_key:
        try:
            configure_dspy(api_key=api_key)
        except Exception as e:
            print(f"⚠️  Auto-configuration failed: {e}")
            print("   Call configure_dspy() manually to set up DSPy.")


# Run auto-configuration
auto_configure()


if __name__ == "__main__":
    print("="*70)
    print(" DSPy Configuration Test")
    print("="*70)
    
    # Test configuration
    if is_configured():
        print("\n✅ DSPy is already configured!")
    else:
        print("\n⚠️  DSPy not configured. Attempting configuration...")
        success = configure_dspy()
        
        if success:
            print("\n✅ Configuration successful!")
        else:
            print("\n❌ Configuration failed!")
            exit(1)
    
    # Test LLM
    print("\n" + "="*70)
    print(" Testing LLM Connection")
    print("="*70)
    
    try:
        llm = get_dspy_llm()
        if llm:
            print("\n✅ LLM instance retrieved successfully!")
            print(f"   Model: {llm.kwargs.get('model', 'unknown')}")
        else:
            print("\n❌ Failed to get LLM instance!")
    except Exception as e:
        print(f"\n❌ Error testing LLM: {e}")
    
    # Test OpenAI client
    print("\n" + "="*70)
    print(" Testing OpenAI Client")
    print("="*70)
    
    try:
        client = get_openai_client()
        if client:
            models = client.models.list()
            print(f"\n✅ OpenAI client connected! Found {len(models.data)} models available.")
        else:
            print("\n❌ Failed to get OpenAI client!")
    except Exception as e:
        print(f"\n❌ Error testing client: {e}")
    
    print("\n" + "="*70)
    print(" ✅ All tests completed!")
    print("="*70)
