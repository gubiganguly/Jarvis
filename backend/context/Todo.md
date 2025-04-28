📋 Ultra-Detailed, Cursor-Ready, Step-by-Step To-Do List + Testing Steps (v3)

0. Accounts & Setup
✅ No coding, manual setup:
Railway / Render account


VAPI.ai account


OpenAI account


Notion API integration


ChromaDB ready (or Docker installed)


✅ Test: Confirm you have the necessary API keys ready and accessible.

1. Initialize Project
✅ Manual setup:
Create /Jarivs


Inside /backend/
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn openai langchain notion-client chromadb python-jose
✅ Test:
 Run this command inside /backend/:
uvicorn main:app --reload

It should error (because main.py doesn't exist yet), but no module errors should happen.

2. Create FastAPI Skeleton (Backend)
Cursor Prompt:
Create a FastAPI app called `main.py` that initializes a simple server with three routes:

- GET `/health` that returns {"status": "ok"}
- POST `/vapi-webhook` that accepts a JSON payload from VAPI.ai containing live transcription
- POST `/memory/save` that saves user memories

Organize it so that in the future we can add `services`, `utils`, and `models` folders cleanly.
Use pydantic models for request validation. Include CORS middleware allowing all origins.

✅ Test:
Start server: uvicorn main:app --reload


Go to browser → http://localhost:8000/health


Should return:
{"status": "ok"}

Confirm /vapi-webhook and /memory/save accept POST requests (even if they don't do anything yet).



3. Integrate VAPI Webhook for Voice Stream
Cursor Prompt:
Extend `main.py`. Create a `/vapi-webhook` POST endpoint that:
- Accepts a payload containing partial transcription chunks from VAPI.
- Buffers the text in memory (dictionary per session ID).
- After a pause of 2-5 seconds of no speech (simulate for now), it finalizes the buffered text and sends it for processing to an internal function `process_transcription(text: str)`.
Make sure you use session IDs to track different conversations.

✅ Test:
Send dummy POST request to /vapi-webhook with:
{"session_id": "abc123", "text": "buy milk"}
Confirm it buffers text correctly.


Simulate a "pause" (wait 2–5 seconds or call finalize manually).


Confirm process_transcription is triggered with correct text.



4. Setup OpenAI GPT-4o Connection (Text Understanding)
Cursor Prompt:
Create a service in `/services/llm_service.py` that:
- Initializes OpenAI API connection using an environment variable `OPENAI_API_KEY`.
- Creates three functions:
    1. `classify_text(text: str) -> str`
    2. `summarize_text(text: str) -> str`
    3. `extract_metadata(text: str) -> dict`
Functions should send a system prompt to GPT-4o with clear instructions.

✅ Test:
Manually call classify_text("Buy milk tomorrow") from a Python script.


You should get "task".


Call summarize_text("I want to start a voice bot agency and take over the world").


Should summarize into one sentence.


Call extract_metadata("Buy milk tomorrow").


Should return due date and category info.



5. Organize Parsed Output
✅ (No external calls needed — combine the outputs into one dict.)
✅ Test:
Write dummy input "Start drone racing brand SkyRacer"


Run through full chain:


Classify → Summarize → Extract Metadata


Confirm the combined dict looks like:
{
  "type": "idea",
  "content": "Start drone racing brand SkyRacer",
  "metadata": {
    "priority": "medium",
    "due_date": null,
    "category": "drones"
  }
}


6. Save into Notion API
Cursor Prompt:
Create a service `/services/notion_service.py` that:
- Connects to Notion API using a token from environment variable `NOTION_API_KEY`.
- Defines functions to create pages in:
  1. Ideas Database
  2. Tasks Database
  3. Reminders Database
  4. Facts Memory Database
- Each function should accept structured dict input and map it to appropriate Notion page format.

✅ Test:
Hardcode a simple dict:
idea = {
    "title": "SkyRacer Drone Brand",
    "category": "Drones",
    "notes": "Create a social media brand for FPV drones."
}

Call create_idea_page(idea) function.


Check Notion workspace — it should create a new entry in the Ideas database.



7. Save Facts into ChromaDB (Memory Persistence)
Cursor Prompt:
Create a service `/services/memory_service.py` that:
- Initializes a ChromaDB database locally.
- Provides functions to:
    1. Save memory fact (text string + metadata)
    2. Query memories (given a query string)
Embed facts before saving using OpenAI embeddings API.

✅ Test:
Save fact "I don't like apples".


Save fact "I love drones".


Search for "fruit", should retrieve "I don't like apples" semantically.


Search for "aerial hobbies", should retrieve "I love drones".



8. Memory Retrieval (Light RAG Search)
✅ Extend /services/memory_service.py.
✅ Test:
Search "drones" after adding 5–10 dummy facts.


Confirm top 5 most similar memories are retrieved and scored.



9. Authentication (JWT) (Optional for MVP)
✅ (Skip for now unless building multi-user.)
✅ Future Test:
Protected endpoint access requires valid JWT.



10. Deploy Backend (Railway/Render)
✅ Manual Deploy:
✅ Test:
After deployment, go to:


https://your-app-url/health


Should return:
{"status": "ok"}

Confirm /vapi-webhook and /memory/save are reachable.



11. (Optional) Build Frontend Dashboard
Cursor Prompt:
Create a simple Next.js frontend app.
- `/dashboard` route
- Fetch brainstorms, tasks, reminders via FastAPI endpoints
- Display in clean TailwindCSS cards
Use SWR for data fetching.

✅ Test:
Visit /dashboard


Confirm list of:


Latest ideas


Latest tasks


Upcoming reminders



12. (Optional) Scheduled Memory Summaries
Cursor Prompt:
In FastAPI backend, add `apscheduler` job:
- Every day at 8pm server time
- Query brainstorms from Notion
- Summarize them into a paragraph using LLM
- Save summary into Notion Daily Logs database

✅ Test:
Manually trigger scheduler.


Confirm a daily log entry is created in Notion summarizing today's brainstorms.



📂 Final Structure Reminder
/Jarvis
  /backend
    main.py
    /services
      llm_service.py
      memory_service.py
      notion_service.py
    /utils
      buffer_manager.py
    /models
      transcription.py
  /frontend (optional)
    Next.js app


🔥 Final Notes
✅ Every major step has a clear test.
✅ After every section, you know if you're still on track.
✅ No big surprises at the end!


