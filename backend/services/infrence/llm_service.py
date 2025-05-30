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
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv
from logging_config import logger
import json

load_dotenv(override=True)  # Load environment variables from .env file
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
if not os.environ.get("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY environment variable is not set")

async def classify_text(text: str) -> str:
    """Classifies the provided text using GPT-4o.
    
    Maps natural speech to specific content types based on Jarvis's purpose as a personal memory assistant.
    Categories align with Notion database organization for automatic routing of voice inputs.
    """
    logger.debug(f"Classifying text: {text[:50]}...")
    try:
        response = await client.chat.completions.create(
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

async def summarize_text(text: str) -> str:
    """Summarizes the provided text using GPT-4o.
    
    Creates concise versions of longer voice inputs to maintain clarity in the Notion database.
    Particularly valuable for lengthy brainstorming sessions or complex ideas, making them
    more browsable and digestible when reviewing later.
    """
    response = await client.chat.completions.create(
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

async def extract_metadata(text: str) -> dict:
    """Extracts metadata from the provided text using GPT-4o.
    
    Powers the intelligent organization capabilities of Jarvis by identifying key elements:
    - Entities (people, organizations) for relationship tracking
    - Dates for reminders and scheduling
    - Keywords and topics for categorization
    - Sentiment for emotional context
    
    This structured metadata enables automatic organization into appropriate Notion databases
    without manual tagging or formatting.
    """
    response = await client.chat.completions.create(
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
    
    return json.loads(response.choices[0].message.content)

async def title_text(text: str) -> str:
    """Generates a concise title for the provided text using GPT-4o.
    
    Creates short, descriptive titles for memories to improve browsability
    and quick identification in the database.
    """
    response = await client.chat.completions.create(
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

async def detect_intent(text: str) -> str:
    """Detects the intent of the provided text using GPT-4o.
    
    Determines if the user's message is related to memory storage, retrieval, or general conversation.
    """
    response = await client.chat.completions.create(
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

async def extract_retrieval_filters(text: str) -> dict:
    """Extracts retrieval filters from the provided text using GPT-4o if using retrieval intent.
    
    Parses user retrieval requests to determine specific memory types and time ranges.
    """
    response = await client.chat.completions.create(
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
    return json.loads(response.choices[0].message.content)

async def summarize_retrieved_memories(memories: list) -> str:
    """Summarizes a list of memories into a brief paragraph."""
    response = await client.chat.completions.create(
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

async def generate_conversational_response(result: dict, original_text: str = "") -> str:
    """Generates a conversational response based on the processing result.
    
    Handles different intents (Neither, Save, Retrieve) with appropriate response styles.
    """
    intent = result.get("intent", "Neither")
    
    if intent == "Neither":
        # For general conversation - use original text directly
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are Jarvis, a helpful and friendly AI assistant. Respond conversationally to the user's message."
                },
                {"role": "user", "content": original_text}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
        
    elif intent == "Save":
        # For memory saves
        memory_type = result.get("type", "memory")
        memory_title = result.get("title", "your thought")
        
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": f"You are Jarvis, a helpful AI assistant. The user just shared something that was saved as a {memory_type} with the title '{memory_title}'. Acknowledge this briefly in a friendly way and respond to their input conversationally."
                },
                {"role": "user", "content": result.get("content", "")}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
        
    elif intent == "Retrieve":
        # For memory retrievals
        query = result.get("query", "")
        memories = result.get("results", [])
        
        if not memories:
            return "I searched your memories but couldn't find anything matching your request. Is there something else I can help you with?"
        
        # Compile memories into context
        memory_context = "\n\n".join([
            f"Memory: {m.get('title', 'Untitled')}\nType: {m.get('type', 'Note')}\nContent: {m.get('content', 'No content')}"
            for m in memories
        ])
        
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are Jarvis, a helpful AI assistant with access to the user's memory database. The user asked a question, and you've retrieved some relevant memories. Using ONLY the provided memories, respond conversationally as if you're having a natural discussion. Don't mention the technical aspects of memory retrieval - just incorporate the information naturally."
                },
                {"role": "system", "content": f"User query: {query}\n\nRetrieved memories:\n{memory_context}"}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    
    return "I'm not sure how to respond to that. How can I help you today?"

async def generate_conversational_response_streaming(result: dict, original_text: str = ""):
    """Generates a streaming conversational response based on the processing result."""
    intent = result.get("intent", "Neither")
    
    system_prompt = ""
    user_prompt = ""
    
    if intent == "Neither":
        system_prompt = "You are Jarvis, a helpful and friendly AI assistant. Respond conversationally to the user's message."
        user_prompt = original_text
    elif intent == "Save":
        memory_type = result.get("type", "memory")
        memory_title = result.get("title", "your thought")
        system_prompt = f"You are Jarvis, a helpful AI assistant. The user just shared something that was saved as a {memory_type} with the title '{memory_title}'. Acknowledge this briefly in a friendly way and respond to their input conversationally."
        user_prompt = result.get("content", "")
    elif intent == "Retrieve":
        query = result.get("query", "")
        memories = result.get("results", [])
        
        if not memories:
            # For special case with no memories, return a simple string
            # This will be handled specially in the caller
            return "I searched your memories but couldn't find anything matching your request. Is there something else I can help you with?"
        
        memory_context = "\n\n".join([
            f"Memory: {m.get('title', 'Untitled')}\nType: {m.get('type', 'Note')}\nContent: {m.get('content', 'No content')}"
            for m in memories
        ])
        
        system_prompt = "You are Jarvis, a helpful AI assistant with access to the user's memory database. The user asked a question, and you've retrieved some relevant memories. Using ONLY the provided memories, respond conversationally as if you're having a natural discussion. Don't mention the technical aspects of memory retrieval - just incorporate the information naturally."
        user_prompt = f"User query: {query}\n\nRetrieved memories:\n{memory_context}"
    
    # Stream the response - use await here now
    response_stream = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7,
        stream=True
    )
    
    return response_stream

