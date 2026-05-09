# Intelligent Voice Parser Service Architecture

The **Intelligent Voice Parser Service** is a real-time speech-to-text engine built with Python and FastAPI. It serves as the auditory core of the NextGenQA platform, converting live meeting audio into structured, speaker-labeled transcripts and facilitating real-time communication between participants.

## 🚀 Key Responsibilities
- **Real-Time Transcription**: Integrates with Azure Cognitive Services to provide low-latency live captions.
- **Meeting Management**: Handles the creation and joining of meeting rooms with secure passcodes.
- **WebSocket Orchestration**: Manages persistent connections for audio streaming, chat, and live updates.
- **Stateless Authentication**: Verifies users independently using a shared `AUTH_SECRET` and JWTs issued by the Auth Service.

---

## 🌟 Service Features

### 1. Real-Time Collaborative Transcription
- **Live Captions**: Streams text segments immediately as they are recognized by Azure.
- **Partial Results**: Displays "typing" text in real-time before sentences are finalized.
- **Speaker Diarization**: Automatically labels text with the speaker's name and role (e.g., "John Doe (Developer)").

### 2. Intelligent Meeting Management
- **Instant Rooms**: Create and join meetings with unique IDs and secure passcodes.
- **Participant Tracking**: Live broadcast of who is currently active in the meeting.
- **History Sync**: New participants automatically receive previous chat history upon joining.

### 3. Integrated Communication
- **Meeting Chat**: In-meeting text messaging that is persisted alongside the transcript.
- **Auto-Persistence**: Every finalized caption is saved to Supabase instantly to prevent data loss.
- **Transcript Finalization**: One-click consolidation of real-time captions into a structured final transcript for post-meeting analysis.

### 4. Advanced Analysis (Extendable)
- **AI Summary**: Built-in hooks for generating meeting summaries.
- **Action Item Extraction**: Identifies key tasks discussed during the call.

---

## 🛠️ Technology Stack
- **Runtime**: Python 3.10+
- **Framework**: FastAPI (Asynchronous Web Framework)
- **Transcription**: Azure Cognitive Services (Speech SDK)
- **Real-Time**: WebSockets (Standard & Binary)
- **Database**: Supabase (via `persistence` layer)

---

## 📊 Database Schema

The service uses a dedicated schema (default: `nextgen_speech_service`) to isolate meeting and transcription data.

### 1. `meetings` Table
Manages the lifecycle of meeting rooms.
| Column | Type | Description |
| :--- | :--- | :--- |
| `meeting_id` | `text` (PK) | Unique 9-character ID |
| `name` | `text` | Display name of the meeting |
| `host_id` | `text` | ID of the user who created it |
| `passcode` | `text` | 6-digit access code |
| `status` | `text` | `active` or `stopped` |

### 2. `speech_captions` Table
Stores real-time, granular transcription results.
| Column | Type | Description |
| :--- | :--- | :--- |
| `caption_id` | `text` (PK) | Unique identifier for the caption line |
| `session_id` | `text` | References the `meeting_id` |
| `speaker` | `text` | Label of the person speaking |
| `text` | `text` | Transcribed text content |

### 3. `meeting_chats` Table
Persistent storage for in-meeting chat messages.
| Column | Type | Description |
| :--- | :--- | :--- |
| `meeting_id` | `text` | References `meetings.meeting_id` |
| `sender` | `text` | Name of the sender |
| `text` | `text` | Message content |

### 4. `transcripts` & `transcript_utterances`
Used for storing final, post-processed transcription payloads with timing metadata and speaker confidence scores.

---

## 🔄 Core Workflows

### 1. The Transcription Pipeline
The service uses a "Push-Stream" architecture to handle audio data:
1. **Audio Ingest**: The frontend sends raw binary audio chunks over a WebSocket.
2. **Azure Integration**: These chunks are pushed into an Azure `PushAudioStream`.
3. **Processing**: Azure's `SpeechRecognizer` performs continuous recognition in the background.
4. **Broadcast**: Partial and final results are broadcasted to all participants in the meeting room via the WebSocket loop.

### 2. Meeting Lifecycle
- **Create**: Generates a unique 9-character Meeting ID and a 6-digit passcode.
- **Join**: Validates the passcode and establishes a WebSocket session.
- **Sync**: Automatically broadcasts participant lists and historical chats upon joining.

---

## 🛡️ Security & Authentication
This service implements the **Shared Secret Pattern**:
- It does **not** call the Auth Service to verify tokens.
- It reads the `AUTH_SECRET` from its own `.env`.
- Using this secret, it decodes the `Authorization: Bearer <token>` header to extract the `user_id` and `role`.

---

## 📁 Project Structure
- **`api/routes.py`**: The "Brain" of the service. Contains meeting logic and the complex WebSocket loop handling audio streams and Azure callbacks.
- **`clients/azure_speech_client.py`**: Encapsulates Azure Speech SDK configuration and stream creation.
- **`persistence/speech_persistence.py`**: Handles all CRUD operations for meetings, captions, and chats in Supabase.
- **`storage/session_store.py`**: An in-memory store to track active WebSocket connections and participants for each meeting.
- **`core/config.py`**: Manages environment variables (Azure keys, Auth Secret, etc.).

---

## 🛠️ Local Development
1. Navigate to `/Intelligent-voice-parser-service`.
2. Install dependencies: `pip install -r requirements.txt`.
3. Configure `.env` with `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, and `AUTH_SECRET`.
4. Start the service: `python main.py`.
5. WebSocket URL: `ws://localhost:8000/ws/{meeting_id}`.
