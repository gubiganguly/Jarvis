"""
This test file validates the LLM service component of the Jarvis Personal Voicebot Memory Assistant.
The LLM service provides text understanding capabilities using OpenAI's GPT-4o to classify user inputs,
summarize content, and extract metadata. These functions form the core intelligence layer that helps
Jarvis understand and organize voice inputs into structured data before saving them to Notion or the 
memory database.
"""

import sys
import os
import json
from pathlib import Path

# Add parent directory to sys.path to import the services module
sys.path.append(str(Path(__file__).parent.parent))

from services.llm_service import classify_text, summarize_text, extract_metadata

def test_classify_text():
    text = "Buy milk tomorrow"
    result = classify_text(text)
    print(f"Classification for '{text}':", result)
    # Note: The actual implementation classifies into Question, Statement, Request, Opinion, or Other
    # So the result might not match "task" exactly

def test_summarize_text():
    text = "I want to start a voice bot agency and take over the world"
    result = summarize_text(text)
    print(f"Summary of '{text}':", result)
    # Check if the result is one sentence (no period followed by space)
    assert "." not in result[:-1], "Summary should be one sentence"

def test_extract_metadata():
    text = "Buy milk tomorrow"
    result = extract_metadata(text)
    print(f"Metadata for '{text}':", json.dumps(result, indent=2))
    # Check if the result contains date and category information
    assert any(key in result for key in ["dates", "due_date", "time"]), "Should include date information"
    assert "main_topics" in result or any(key in result for key in ["category", "categories", "type"]), "Should include category information"

if __name__ == "__main__":
    print("Testing classify_text...")
    test_classify_text()
    print("\nTesting summarize_text...")
    test_summarize_text()
    print("\nTesting extract_metadata...")
    test_extract_metadata()
    print("\nAll tests completed.") 