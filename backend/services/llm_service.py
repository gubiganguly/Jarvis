"""
LLM Service for Jarvis Personal Voicebot Memory Assistant.

This service provides natural language understanding capabilities using OpenAI's GPT-4o model.
It processes user voice inputs by classifying text type, summarizing content, and extracting
structured metadata. These functions enable Jarvis to intelligently organize spoken ideas,
tasks, and reminders before saving them to Notion or the memory database.

Part of the Jarvis "Brain Extension" system that captures voice inputs and automatically
organizes them into structured formats. This LLM service powers the intelligence layer
that transforms raw transcribed speech into categorized, tagged content ready for storage
in Notion databases or ChromaDB for persistent memory and easy retrieval.
"""

# NOTE: Make async later

import os
from openai import OpenAI
from dotenv import load_dotenv
from logging_config import logger

load_dotenv(override=True)  # Load environment variables from .env file
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
if not os.environ.get("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY environment variable is not set")

def classify_text(text: str) -> str:
    """Classifies the provided text using GPT-4o.
    
    Maps natural speech to specific content types based on Jarvis's purpose as a personal memory assistant.
    Categories align with Notion database organization for automatic routing of voice inputs.
    """
    logger.debug(f"Classifying text: {text[:50]}...")
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system", 
                    "content": """You are a classifier for a personal voicebot memory assistant. Categorize the input text into ONE of these categories:
                    
                    - Business Idea: New venture concepts, product ideas, business models, startup opportunities, or market strategies that could be developed into commercial ventures
                    - Task: Actionable items requiring completion with clear outcomes (e.g., "buy groceries," "finish report," "call plumber"), typically not linked to specific calendar dates
                    - Reminder: Time-sensitive notifications about future events, appointments, deadlines, or important dates that require attention at a specific time ("dentist on Tuesday," "pay bill by Friday")
                    - Note: General information, observations, reflections, or insights without a specific action required
                    - Places: Locations, venues, destinations, or establishments to visit, remember, or explore in the future
                    - Learn: Topics, skills, subjects, or knowledge areas to study, research, or develop proficiency in
                    - Question: Inquiries, uncertainties, or information gaps requiring future investigation or answers
                    
                    Respond ONLY with the category name."""
                },
                {"role": "user", "content": text}
            ],
            temperature=0.0
        )
        result = response.choices[0].message.content
        logger.debug(f"Classification result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error classifying text: {e}", exc_info=True)
        raise

def summarize_text(text: str) -> str:
    """Summarizes the provided text using GPT-4o.
    
    Creates concise versions of longer voice inputs to maintain clarity in the Notion database.
    Particularly valuable for lengthy brainstorming sessions or complex ideas, making them
    more browsable and digestible when reviewing later.
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system", 
                "content": "You are a text summarizer. Create a concise summary of the provided text, capturing the main points while significantly reducing the length. Your summary should be clear and informative without losing any important details."
            },
            {"role": "user", "content": text}
        ],
        temperature=0.3
    )
    return response.choices[0].message.content

def extract_metadata(text: str) -> dict:
    """Extracts metadata from the provided text using GPT-4o.
    
    Powers the intelligent organization capabilities of Jarvis by identifying key elements:
    - Entities (people, organizations) for relationship tracking
    - Dates for reminders and scheduling
    - Keywords and topics for categorization
    - Sentiment for emotional context
    
    This structured metadata enables automatic organization into appropriate Notion databases
    without manual tagging or formatting.
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system", 
                "content": "You are a metadata extractor. Analyze the provided text and extract key metadata including: entities (people, places, organizations), dates, keywords, sentiment (positive, negative, neutral), and main topics. Return only a JSON object with these fields."
            },
            {"role": "user", "content": text}
        ],
        temperature=0.0,
        response_format={"type": "json_object"}
    )
    
    import json
    return json.loads(response.choices[0].message.content)

def title_text(text: str) -> str:
    """Generates a concise title for the provided text using GPT-4o.
    
    Creates short, descriptive titles for memories to improve browsability
    and quick identification in the database.
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system", 
                "content": "Generate a short, concise title (5-7 words max) that captures the essence of the following text."
            },
            {"role": "user", "content": text}
        ],
        temperature=0.3
    )
    return response.choices[0].message.content

def detect_intent(text: str) -> str:
    """Detects the intent of the provided text using GPT-4o.
    
    Determines if the user's message is related to memory storage, retrieval, or general conversation.
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": """You are an intent classifier for a memory assistant. Given a user message, classify it into ONE of these:
                
                - Save: The user is creating a new memory, idea, task, reminder, or note.
                - Retrieve: The user is trying to retrieve or ask about past memories, ideas, tasks, reminders.
                - Neither: General conversation not related to memory storage or retrieval.

                Respond ONLY with Save, Retrieve, or Neither."""
            },
            {"role": "user", "content": text}
        ],
        temperature=0.0
    )
    return response.choices[0].message.content



def extract_retrieval_filters(text: str) -> dict:
    """Extracts retrieval filters from the provided text using GPT-4o if using retrieval intent.
    
    Parses user retrieval requests to determine specific memory types and time ranges.
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": """You are a retrieval filter extractor for a memory assistant. Given a user's retrieval request, extract:

- memory_type (optional): One of "Business Idea", "Task", "Reminder", "Note", "Places", "Learn", "Question"
- date_from (optional): ISO 8601 format (e.g., 2024-04-01)
- date_to (optional): ISO 8601 format (e.g., 2024-04-30)

If no information is found, leave the fields null. Return a JSON object."""
            },
            {"role": "user", "content": text}
        ],
        temperature=0.0, 
        response_format={"type": "json_object"}
    )
    import json
    return json.loads(response.choices[0].message.content)


def summarize_retrieved_memories(memories: list) -> str:
    """Summarizes a list of memories into a brief paragraph."""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You are a memory summarizer. Given a list of user memories, summarize them into a coherent paragraph (2–4 sentences) capturing the major themes and topics the user thought about."
            },
            {"role": "user", "content": "\n".join(memories)}
        ],
        temperature=0.3
    )
    return response.choices[0].message.content

