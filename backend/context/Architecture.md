# 📐 Full Architecture Plan — "Personal Voice Memory Assistant"

---

## 1. Core Components

| Component                 | Purpose                                        | Tools (MVP-Optimized) |
|----------------------------|------------------------------------------------|-----------------------|
| **Voice Capture**          | Capture live voice, real-time transcription    | VAPI.ai (mic, streaming, diarization) |
| **Memory and Retrieval Engine** | Organize + recall ideas/tasks + personality memories | RAG powered by ChromaDB or LanceDB |
| **LLM for Understanding and Structuring** | Parse ideas, classify into categories (business idea, reminder, task) | OpenAI GPT-4o or Mistral |
| **Knowledge Base Storage** | Store information in structured way for browsing | Notion API |
| **Persistent User Memory** | Save small facts about the user ("I don't like apples") | ChromaDB + Redis or SQLite |
| **Agent Framework**        | Manage LLM chains (brainstorming, task creation, memory saving) | LangChain (light usage) |
| **Server/Backend**         | Handle orchestration between voice, LLMs, Notion, DBs | FastAPI (Python) |
| **Authentication**         | Protect access, identify the user | JWT Tokens |
| **Optional: Frontend Dashboard** | Small dashboard to see latest memory captures | Next.js + TailwindCSS |

---

## 2. System Flow

### Realtime Speaking
- User speaks → VAPI.ai captures → real-time text stream →  
  1. Check if intent is task, idea, reminder, or fact  
  2. Parse & organize via LLM  
  3. Update memory (ChromaDB) and/or Notion DB  

### Memory Retrieval while Speaking (RAG)
- During conversation:  
  - Small RAG pulls based on latest user context.  
  - Example: _"Hey, last time you mentioned a drone brand idea called SkyRacer..."_

### Memory Saving After Speaking
- After user stops talking:
  - LLM cleans the conversation
  - Organizes into structured format
  - Inserts into Notion

---

## 3. MVP Feature Priorities

| Feature                         | MVP Priority | How to Build |
|----------------------------------|--------------|--------------|
| **Voice capture → text**         | Critical     | VAPI.ai stream with Whisper backend |
| **Idea/task classification**    | Critical     | LLM prompt: "Classify into idea/task/reminder/fact" |
| **Save to Notion**               | Critical     | Notion API - create database pages automatically |
| **Persistent user facts**        | High         | Store key-value facts in ChromaDB |
| **Retrieval during conversations** | Medium    | Pull last 5 relevant facts/ideas via Chroma semantic search |
| **Periodic memory review**      | Nice to have | Scheduled Notion summary or API call |
| **Small dashboard**             | Later        | Next.js frontend to view memories/tasks |

---

## 4. LLM Design Strategy

- **Stream transcriptions** and **batch** when user pauses (~2–5s window)
- **Small chained prompts**:
  - Detect: _Is this a task / idea / reminder / fact?_
  - Summarize if needed
  - Extract metadata (category, priority, due date)
  - Push directly to Notion or memory storage

---

## 5. High-Level Tech Stack

| Purpose                     | Tool           | Reason |
|------------------------------|----------------|--------|
| **Voice to Text**            | VAPI.ai        | Built-in streaming, diarization |
| **Text understanding**       | OpenAI GPT-4o  | Best generalist, fast multi-tasking |
| **Memory/Fact storage**      | ChromaDB       | Lightweight, easy to query |
| **Short-term Key-Value Memory** | SQLite or Redis | Extremely fast |
| **Long-term Memory Display** | Notion         | Familiar UI, massive time saver |
| **API Backend**              | FastAPI        | Async-ready, easy to deploy |
| **Agent/Chain Management**   | LangChain      | Lightweight RAG + LLM workflows |
| **Hosting**                  | Railway.app / Render.com | Simple cloud hosting |
| **Authentication**           | JWT (PyJWT)    | Lightweight user sessions |

---

## 6. Timeline to MVP

| Week    | Goal |
|---------|------|
| **Week 1** | Set up VAPI capture → FastAPI backend → OpenAI connection |
| **Week 2** | Build LLM parsing chain → Insert into Notion automatically |
| **Week 3** | Implement small memory store → Save user facts ("I like chocolate") |
| **Week 4** | Add retrieval (RAG) → Make context-aware during conversations |
| **(Optional)** | Deploy backend → Add small dashboard (Next.js) |

---

## 🚀 Quick First MVP System Diagram

[Microphone]
    ↓
[VAPI (Voice API)]
    ↓
[Transcription Stream]
    ↓
[FastAPI Backend]
    ↓
[LLM Call - classify/summarize/input task]
    ↓
    → [Notion API] (for structured notes)
    → [ChromaDB] (for memory facts + RAG)


---

## 🛠️ Tools You Will Need to Set Up

- [ ] VAPI.ai account
- [ ] OpenAI API Key (or Mistral if you want cheaper)
- [ ] Notion developer integration (easy, generate API key)
- [ ] ChromaDB (local to start)
- [ ] Railway / Render accounts for deployment
- [ ] (Optional) Next.js template for frontend dashboard later
