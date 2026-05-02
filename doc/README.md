# API Documentation

This directory contains the Postman collection for testing the **Intelligent Voice Parser Service**.

## Postman Collection
The file `postman_collection.json` can be imported directly into Postman.

### Setup
1. **Import**: Open Postman -> Import -> Select `postman_collection.json`.
2. **Variables**: The collection uses the following variables:
   - `base_url`: Defaults to `http://localhost:8001` (Voice Service).
   - `auth_token`: Your Supabase JWT. You must set this in the collection variables or environment.
   - `meeting_id`: Used for meeting-specific requests.
   - `passcode`: Used for joining meetings.

### Key Features
- **Meeting Orchestration**: Create and join virtual rooms for collaboration.
- **Real-time Transcription**: Live voice-to-text via AssemblyAI WebSockets.
- **Persistent Chat**: Send and retrieve messages that stay linked to the meeting.
- **AI Analysis**: Generate summaries and action items from meeting data.

### Authentication
Every request (except health) requires an `Authorization: Bearer <token>` header. This token must be a valid JWT issued by the **Auth Service** (Port 8000).

### WebSocket Connection
Connect to `ws://localhost:8001/ws/{{meeting_id}}?name={{your_name}}` for real-time audio and chat streaming.
