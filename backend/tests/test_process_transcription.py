import pytest
import os
import json
import sys
from unittest.mock import patch

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import process_transcription

test_cases = [
    # Ambiguous category example
    "I need to remember to research startup funding models tomorrow, which could help with my SaaS idea, but also relates to that online course I'm taking about venture capital.",
    
    # Complex, multi-part example
    "So I was thinking about that AI project we discussed last week with Sarah from OpenMind Corp. We should schedule a follow-up meeting on June 15th to discuss implementation details. Also, don't forget we need to submit the grant proposal by the end of this month. The key focus areas should be natural language processing, computer vision, and ethical considerations especially around data privacy. I'm feeling optimistic about our chances but concerned about the timeline.",
    
    # Task with reminders and specifics
    "Pick up milk, eggs, and bread on the way home. Also need to call mom about her birthday on Saturday. Remember to book flights for the conference in Boston happening September 12-15. The confirmation code for the hotel reservation is BH29856.",
    
    # Mixed content with place references
    "That restaurant we tried in Chicago, Lou Malnati's, had amazing deep dish pizza. We should definitely go back there next time we're in town. Maybe in November when we visit for John and Lisa's wedding. Also, make sure to check out their new location downtown.",
    
    # Empty/short example
    "Remember this.",
]

def save_results(results, output_file="test_results.json"):
    """Save test results to a JSON file"""
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
def test_process_transcription():
    """Test the process_transcription function with various inputs"""
    results = []
    
    for i, test in enumerate(test_cases):
        print(f"\n===== TEST CASE {i+1} =====")
        print(f"INPUT: {test[:100]}..." if len(test) > 100 else f"INPUT: {test}")
        
        try:
            result = process_transcription(test)
            print(f"CLASSIFICATION: {result['type']}")
            print(f"SUMMARY: {result['content']}")
            print("METADATA:")
            for key, value in result['metadata'].items():
                print(f"  {key}: {value}")
                
            results.append({
                "input": test,
                "output": result
            })
            
            # Basic assertions to ensure the function is working properly
            assert "type" in result, "Result missing classification type"
            assert "content" in result, "Result missing content summary"
            assert "metadata" in result, "Result missing metadata"
            
        except Exception as e:
            print(f"ERROR: {str(e)}")
            pytest.fail(f"Test case {i+1} failed with error: {str(e)}")
    
    # Optionally save results for further analysis
    if os.environ.get("SAVE_RESULTS", "").lower() == "true":
        save_results(results)

if __name__ == "__main__":
    # When run directly, execute without pytest
    if not os.environ.get("OPENAI_API_KEY"):
        print("WARNING: OPENAI_API_KEY environment variable not set. Tests may fail.")
        
    for i, test in enumerate(test_cases):
        print(f"\n===== TEST CASE {i+1} =====")
        print(f"INPUT: {test[:100]}..." if len(test) > 100 else f"INPUT: {test}")
        
        try:
            result = process_transcription(test)
            print(f"CLASSIFICATION: {result['type']}")
            print(f"SUMMARY: {result['content']}")
            print("METADATA:")
            for key, value in result['metadata'].items():
                print(f"  {key}: {value}")
        except Exception as e:
            print(f"ERROR: {str(e)}")