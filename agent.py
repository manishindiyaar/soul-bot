import asyncio
from typing import Annotated
import os
import logging
import json
import inspect
from datetime import datetime
from functools import wraps
import sys  # <-- ADDED
from livekit import agents, rtc
from livekit.agents import JobContext, WorkerOptions, cli, tokenize, tts
from livekit.agents.llm import ChatContext, ChatImage, ChatMessage
from dotenv import load_dotenv
from livekit.agents.voice_assistant import VoiceAssistant
from livekit.plugins import deepgram, openai, silero

# Make sure Python can find your email_send.py file:
sys.path.append(r"C:\Users\Aadidev\Desktop\SoulBotHackathon\email_send")
from email_send import email_send

# ----------------- ADD: Import your Supabase helper function -----------------
# Suppose you have the Python code from "supabase.py" or "patient_service.py"
# that defines get_last_inserted_patient().
sys.path.append(r"C:\Users\Aadidev\Desktop\SoulBotHackathon\backend\supabase_helper.py")  # Adjust if needed
from supabase_helper import get_last_inserted_patient  # <-- rename if needed

# Load environment variables
load_dotenv(dotenv_path=".env.local")

class AssistantFunction(agents.llm.FunctionContext):
    """This class is used to define functions that will be called by the assistant."""
    @agents.llm.ai_callable(
        description=(
            "Called when asked to evaluate something that would require vision capabilities,"
            "for example, an image, video, or the webcam feed."
        )
    )
    async def image(
        self,
        user_msg: Annotated[
            str,
            agents.llm.TypeInfo(
                description="The user message that triggered this function"
            ),
        ],
    ):
        return None

async def get_video_track(room: rtc.Room):
    """Get the first video track from the room."""
    video_track = asyncio.Future[rtc.RemoteVideoTrack]()
    for pid, participant in room.remote_participants.items():
        for tid, track_publication in participant.track_publications.items():
            if track_publication.track is not None and isinstance(
                track_publication.track, rtc.RemoteVideoTrack
            ):
                video_track.set_result(track_publication.track)
                break
    return await video_track

async def entrypoint(ctx: JobContext):
    await ctx.connect()

    # 1) Prepare your base chat context with a default system message
    chat_context = ChatContext(
        messages=[
            ChatMessage(
                role="system",
                content=(
                    """
You are a Kundali and horoscope chatbot providing concise, natural, and accurate insights.

Keep responses to 2 sentences unless detailed analysis is requested. Ask if they want Kundali or horoscope details,
or a summary of both. Ask about career, relationships, personal growth, etc. Offer daily/monthly horoscopes,
gemstone suggestions, rituals, and do’s/don’ts. Ask if they want meditation or workout suggestions.
Keep it conversational and empathetic.
                    """
                ),
            )
        ]
    )

    # 2) Fetch data from Supabase and inject it into the system prompt
    last_patient = get_last_inserted_patient()
    if last_patient:
        # Extract fields; adjust if your field names differ
        name = last_patient.get("full_name", "Unknown")
        email = last_patient.get("email", "Unknown")
        medical_problem = last_patient.get("medical_problem", "None")
        
        # Append them to system prompt for personalization
        old_system_text = chat_context.messages[0].content
        personalized_block = f"""
Patient details from Supabase:
  - Name: {name}
  - Email: {email}
  - Medical Problem: {medical_problem}
"""
        # Build new system prompt
        new_system_text = old_system_text + personalized_block
        chat_context.messages[0].content = new_system_text
    else:
        print("No patient data found from Supabase.")

    # Path for storing logs
    LOG_FOLDER = r"C:\Users\Aadidev\Desktop\SoulBotHackathon\backend\conversation logs"

    azuregpt = openai.LLM.with_azure(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version="2024-08-01-preview",
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        model="gpt-4"
    )

    latest_image: rtc.VideoFrame | None = None

    assistant = VoiceAssistant(
        vad=silero.VAD.load(),
        stt=deepgram.STT(),
        llm=azuregpt,
        tts=deepgram.TTS(model="aura-stella-en"),
        fnc_ctx=AssistantFunction(),
        chat_ctx=chat_context,
    )

    chat = rtc.ChatManager(ctx.room)

    def save_conversation_logs():
        """Save the chat_context.messages to a JSON file in LOG_FOLDER."""
        conversation_data = []
        for msg in chat_context.messages:
            conversation_data.append({
                "role": msg.role,
                "content": msg.content
            })
        os.makedirs(LOG_FOLDER, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"conversation_{timestamp}.json"
        file_path = os.path.join(LOG_FOLDER, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(conversation_data, f, indent=2, ensure_ascii=False)
        print(f"Conversation logs saved to {file_path}")
        return file_path

    async def _answer(text: str, use_image: bool = False):
        """Generate and deliver response to user input."""
        print(f"_answer called with text: {text}")

        # Check if the user typed/spoke "quit"
        if text.strip().lower() == "quit":
            print("User triggered quit command.")
            # 1) Immediately store the conversation logs so we don't lose them
            conversation_log_path = save_conversation_logs()

            # 2) Call your external function to send the email
            try:
                print("Calling email_send()...")
                email_send("aadidevraizada26@gmail.com", "Your Astro Reading")
            except Exception as e:
                print(f"Error calling email_send: {e}")

            # 3) Optionally say goodbye
            await assistant.say("Alright, ending the conversation now. Goodbye!")

            # 4) Now disconnect from the room
            await ctx.room.disconnect()
            return

        # Otherwise, user typed something else
        content: list[str | ChatImage] = [text]
        if use_image and latest_image:
            content.append(ChatImage(image=latest_image))

        # Add user message to the chat context
        chat_context.messages.append(ChatMessage(role="user", content=content))

        # Let LLM produce a response
        stream = azuregpt.chat(chat_ctx=chat_context)
        await assistant.say(stream, allow_interruptions=True)

    @chat.on("message_received")
    def on_message_received(msg: rtc.ChatMessage):
        """Handle text chat messages."""
        if msg.message:
            print(f"Text chat message received: {msg.message}")
            asyncio.create_task(_answer(msg.message, use_image=False))

    @assistant.on("transcription")
    def on_voice_transcription(text: str):
        """Handle voice input (STT)."""
        print(f"Voice transcription: {text}")
        asyncio.create_task(_answer(text, use_image=False))

    @assistant.on("function_calls_finished")
    def on_function_calls_finished(called_functions: list[agents.llm.CalledFunction]):
        """Handle function calls (image analysis, etc.)."""
        for function in called_functions:
            if function.name == "image":
                user_msg = function.call_info.arguments.get("user_msg")
                if user_msg:
                    asyncio.create_task(_answer(user_msg, use_image=True))

    # Start the voice assistant
    assistant.start(ctx.room)
    await asyncio.sleep(1)

    # Initial greeting
    await assistant.say("Hello, I am Soul-Bot. Would you like a kundali or horoscope reading?", allow_interruptions=True)

    try:
        # Keep running while connected
        while ctx.room.connection_state == rtc.ConnectionState.CONN_CONNECTED:
            video_track = await get_video_track(ctx.room)
            async for event in rtc.VideoStream(video_track):
                latest_image = event.frame
    except Exception as e:
        print(f"Exception in the main loop: {e}")
        raise
    finally:
        print("Reached finally block... (fallback save)")
        # If user left unexpectedly or an error occurred, fallback to save logs
        try:
            save_conversation_logs()
        except Exception as ex:
            print(f"Error saving logs in finally block: {ex}")

