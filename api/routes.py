"""API routes for speech-to-text service."""

from __future__ import annotations

from typing import Any
import random
import string
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Header, WebSocket, WebSocketDisconnect
import asyncio
import websockets
import base64
import json

from clients.assemblyai_client import AssemblyAIClient
from core.config import SpeechServiceSettings
from models.schemas import (
    CaptionPushRequest,
    CaptionsResponse,
    MeetingCreateRequest,
    MeetingJoinRequest,
    MeetingResponse,
    UrlTranscriptionRequest,
    UrlTranscriptionResponse,
    VoiceSessionStartResponse,
    VoiceSessionStopRequest,
)
from persistence.speech_persistence import SpeechPersistence
from storage.session_store import SessionStore


def _map_utterances(payload: dict[str, Any], speaker_map: dict[str, str]) -> list[dict[str, Any]]:
    utterances_raw = payload.get("utterances") or []
    return [
        {
            "speaker": speaker_map.get(str(item.get("speaker", "")), f"Speaker {item.get('speaker', 'Unknown')}"),
            "text": item.get("text", ""),
            "start": item.get("start", 0),
            "end": item.get("end", 0),
            "confidence": item.get("confidence", None),
        }
        for item in utterances_raw
    ]


def _map_sentiment(payload: dict[str, Any], speaker_map: dict[str, str]) -> list[dict[str, Any]]:
    sentiment_raw = payload.get("sentiment_analysis_results") or []
    return [
        {
            "text": item.get("text", ""),
            "start": item.get("start", 0),
            "end": item.get("end", 0),
            "speaker": speaker_map.get(str(item.get("speaker", "")), f"Speaker {item.get('speaker', 'Unknown')}"),
            "sentiment": item.get("sentiment", "NEUTRAL"),
            "emotion_hint": {
                "POSITIVE": "confident",
                "NEGATIVE": "frustrated",
                "NEUTRAL": "neutral",
            }.get(str(item.get("sentiment", "NEUTRAL")), "neutral"),
            "confidence": item.get("confidence", None),
        }
        for item in sentiment_raw
    ]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_router(
    store: SessionStore,
    assemblyai: AssemblyAIClient,
    persistence: SpeechPersistence,
    settings: SpeechServiceSettings,
) -> APIRouter:
    """Create API router with injected dependencies."""
    router = APIRouter()

    def get_current_user(authorization: str | None = Header(None)) -> dict[str, Any]:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid or missing authentication token")
        
        token = authorization.replace("Bearer ", "")
        user = persistence._gateway.get_user(token, settings.auth_secret)
        if not user:
            raise HTTPException(status_code=401, detail="User not found or token expired")
        return user

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "speech-to-text"}

    @router.post("/voice/session/start", response_model=VoiceSessionStartResponse)
    def start_voice_session(user: dict = Depends(get_current_user)) -> VoiceSessionStartResponse:
        session_id = store.create_session()
        persistence.create_session(session_id)
        token = assemblyai.create_realtime_token(expires_in_seconds=3600)
        return VoiceSessionStartResponse(session_id=session_id, realtime_token=token)

    @router.post("/voice/session/stop")
    def stop_voice_session(
        body: VoiceSessionStopRequest,
        user: dict = Depends(get_current_user)
    ) -> dict[str, str]:
        store.stop_session(body.session_id)
        persistence.stop_session(body.session_id)
        return {"status": "stopped", "session_id": body.session_id}

    @router.post("/voice/captions/push")
    def push_caption(
        body: CaptionPushRequest,
        user: dict = Depends(get_current_user)
    ):
        caption = store.push_caption(body.session_id, body.speaker, body.text)
        persistence.save_caption(body.session_id, caption)
        return caption

    @router.get("/voice/captions/{session_id}", response_model=CaptionsResponse)
    def get_captions(
        session_id: str,
        user: dict = Depends(get_current_user)
    ) -> CaptionsResponse:
        return CaptionsResponse(session_id=session_id, captions=store.get_captions(session_id))

    @router.post("/voice/transcribe/url", response_model=UrlTranscriptionResponse)
    def transcribe_audio_url(
        body: UrlTranscriptionRequest,
        user: dict = Depends(get_current_user)
    ) -> UrlTranscriptionResponse:
        payload = assemblyai.transcribe_url(
            audio_url=body.audio_url,
            speaker_labels=body.speaker_labels,
            sentiment_analysis=body.sentiment_analysis,
            language_code=body.language_code,
            speech_model=body.speech_model,
        )
        
        # Apply speaker mapping to the payload before saving and returning
        mapped_utterances = _map_utterances(payload, body.speaker_map)
        mapped_sentiment = _map_sentiment(payload, body.speaker_map)
        
        # Update payload for persistence
        payload["utterances"] = mapped_utterances
        payload["sentiment_analysis_results"] = mapped_sentiment
        
        persistence.save_transcription(body.audio_url, payload)

        return UrlTranscriptionResponse(
            transcript_id=str(payload.get("id", "")),
            status=str(payload.get("status", "unknown")),
            text=str(payload.get("text", "")),
            utterances=mapped_utterances,
            sentiment_results=mapped_sentiment,
        )

    @router.post("/meeting/create", response_model=MeetingResponse)
    def create_meeting(
        body: MeetingCreateRequest,
        user: dict = Depends(get_current_user)
    ) -> MeetingResponse:
        meeting_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=9))
        passcode = ''.join(random.choices(string.digits, k=6))
        
        meeting_data = {
            "meeting_id": meeting_id,
            "name": body.name,
            "host_id": user["id"],
            "passcode": passcode,
            "mode": body.mode,
            "status": "active",
            "created_at": _utc_now(),
        }
        
        persistence.save_meeting(meeting_data)
        
        # In a real app, this link would point to your frontend domain
        invite_link = f"http://localhost:5173/login?meetingId={meeting_id}&passcode={passcode}"
        
        return MeetingResponse(
            status="success",
            meeting_id=meeting_id,
            passcode=passcode,
            invite_link=invite_link,
            name=body.name
        )

    @router.post("/meeting/join", response_model=MeetingResponse)
    def join_meeting(
        body: MeetingJoinRequest,
        user: dict = Depends(get_current_user)
    ) -> MeetingResponse:
        meeting = persistence.get_meeting(body.meeting_id)
        
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
            
        if meeting["passcode"] != body.passcode:
            raise HTTPException(status_code=401, detail="Invalid passcode")
            
        return MeetingResponse(
            status="success",
            meeting_id=meeting["meeting_id"],
            passcode=meeting["passcode"],
            invite_link=f"http://localhost:5173/login?meetingId={meeting['meeting_id']}&passcode={meeting['passcode']}",
            name=meeting["name"]
        )

    @router.get("/meeting/{meeting_id}/chats")
    def get_meeting_chats(
        meeting_id: str,
        user: dict = Depends(get_current_user)
    ):
        chats = persistence.get_chats(meeting_id)
        return {"status": "success", "chats": chats}

    @router.get("/meeting/{meeting_id}/transcript")
    def get_meeting_transcript(
        meeting_id: str,
        user: dict = Depends(get_current_user)
    ):
        transcript = persistence.get_meeting_captions(meeting_id)
        return {"status": "success", "transcript": transcript}

    @router.post("/meeting/{meeting_id}/analyze")
    def analyze_meeting(
        meeting_id: str,
        body: dict,
        user: dict = Depends(get_current_user)
    ):
        # type = body.get("type", "summary")
        # In a real app, we would pull the transcript and send to Gemini/GPT-4
        # For now, we'll return a structured mock that demonstrates the feature
        
        analysis_type = body.get("type", "summary")
        
        if analysis_type == "summary":
            return {
                "status": "success",
                "data": "The meeting focused on the migration of session management to the Voice Service. The team discussed the benefits of centralizing real-time state and decided to proceed with the refactor. Key technical challenges included database schema synchronization and WebSocket orchestration."
            }
        elif analysis_type == "action_items":
            return {
                "status": "success",
                "data": [
                    "Update Supabase schema to include meeting_chats table.",
                    "Refactor frontend App.tsx to use React Router.",
                    "Integrate AssemblyAI real-time token generation in the session start flow."
                ]
            }
        
        return {"status": "error", "message": "Unknown analysis type"}

    @router.websocket("/ws/{meeting_id}")
    async def websocket_endpoint(
        websocket: WebSocket,
        meeting_id: str,
        name: str = "Anonymous"
    ):
        await websocket.accept()
        conn_id = str(uuid.uuid4())
        
        # Add to store
        store.add_participant(meeting_id, conn_id, name, websocket)
        
        # Broadcast current participants
        participants = store.get_participants(meeting_id)
        connections = store.get_connections(meeting_id)
        for conn in connections:
            try: await conn.send_json({"type": "participants", "data": participants})
            except: pass

        # AssemblyAI Real-time Integration
        # We wrap this in a try block so the meeting doesn't crash if AAI is offline
        try:
            token = assemblyai.create_realtime_token()
            if not token:
                print("[AAI] ⚠️ Failed to generate transcription token. Check your API key.")
                aai_ws = None
            else:
                aai_url = f"wss://api.assemblyai.com/v2/realtime/ws?sample_rate=16000&token={token}"
                aai_ws = await websockets.connect(aai_url)
                
                async def handle_aai_messages():
                    """Listen for transcription results from AssemblyAI and broadcast them."""
                    try:
                        async for message in aai_ws:
                            msg_data = json.loads(message)
                            if msg_data.get("message_type") in ["PartialTranscript", "FinalTranscript"]:
                                text = msg_data.get("text", "")
                                if not text: continue
                                
                                broadcast_data = {
                                    "type": "transcription",
                                    "data": {
                                        "text": text,
                                        "speaker_id": conn_id,
                                        "speaker_name": name,
                                        "is_final": msg_data.get("message_type") == "FinalTranscript"
                                    }
                                }
                                for conn in store.get_connections(meeting_id):
                                    try: await conn.send_json(broadcast_data)
                                    except: pass
                                    
                                if msg_data.get("message_type") == "FinalTranscript":
                                    persistence.save_caption(meeting_id, CaptionLine(
                                        id=str(uuid.uuid4()),
                                        speaker=name,
                                        text=text,
                                        created_at=_utc_now()
                                    ))
                    except Exception as e:
                        print(f"[AAI] Receiver error: {e}")

                asyncio.create_task(handle_aai_messages())
        except Exception as e:
            print(f"[AAI] ❌ Transcription Service Unavailable: {e}")
            aai_ws = None

        # Main WebSocket Loop
        try:
            while True:
                msg = await websocket.receive()
                
                if "bytes" in msg:
                    # Only forward if AAI is connected
                    if aai_ws and aai_ws.open:
                        audio_b64 = base64.b64encode(msg["bytes"]).decode("utf-8")
                        await aai_ws.send(json.dumps({"audio_data": audio_b64}))
                    
                elif "text" in msg:
                    data = json.loads(msg["text"])
                    if data.get("type") == "chat":
                        text = data.get("text", "")
                        persistence.save_chat(meeting_id, name, text)
                        for conn in store.get_connections(meeting_id):
                            try:
                                await conn.send_json({
                                    "type": "chat",
                                    "data": {
                                        "sender": data.get("sender", name),
                                        "text": text,
                                        "timestamp": _utc_now()
                                    }
                                })
                            except: pass
                    elif data.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            pass
        finally:
            # Cleanup AssemblyAI
            if aai_ws:
                try: 
                    await aai_ws.send(json.dumps({"terminate_session": True}))
                    await aai_ws.close()
                except: pass
            
            # Cleanup Store & Notify others
            store.remove_participant(meeting_id, conn_id, websocket)
            participants = store.get_participants(meeting_id)
            for conn in store.get_connections(meeting_id):
                try: await conn.send_json({"type": "participants", "data": participants})
                except: pass

    return router
