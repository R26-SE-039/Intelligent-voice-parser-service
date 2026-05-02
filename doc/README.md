# API Documentation

This directory contains the Postman collection for testing the **Intelligent Voice Parser Service**.

## Postman Collection
The file `postman_collection.json` can be imported directly into Postman.

### Setup
1. **Import**: Open Postman -> Import -> Select `postman_collection.json`.
2. **Variables**: The collection uses the following variables:
   - `base_url`: Defaults to `http://localhost:8000`.
   - `auth_token`: Your Supabase JWT. You must set this in the collection variables or environment.
   - `session_id`: Used for session-specific requests.

### Key Features Tested
- **Health Check**: Basic service status.
- **Voice Sessions**: Starting and stopping real-time sessions.
- **Captions**: Pushing live text with roles (PO/BA).
- **Transcription**: Full file transcription with **Speaker Mapping** (translating Speaker A/B into PO/BA).

### Authentication
Every request (except health) requires a `Bearer` token. This token should be a valid Supabase JWT for your project.
