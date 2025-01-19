import asyncio
from typing import Annotated
import os
import logging
import json
import inspect
from datetime import datetime
from functools import wraps
from livekit import agents, rtc
from livekit.agents import JobContext, WorkerOptions, cli, tokenize, tts
from livekit.agents.llm import (
    ChatContext,
    ChatImage,
    ChatMessage,
)
from dotenv import load_dotenv
from livekit.agents.voice_assistant import VoiceAssistant
from livekit.plugins import deepgram, openai, silero
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

# Enhanced logging setup
def setup_logging():
    log_directory = "logs"
    if not os.path.exists(log_directory):
        os.makedirs(log_directory)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"{log_directory}/assistant_{timestamp}.log"
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# Decorator for function logging
def log_function_call(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        func_name = func.__name__
        logger.info(f"{'='*50}")
        logger.info(f"ENTERING FUNCTION: {func_name}")
        logger.info(f"Arguments: {args[1:] if len(args) > 1 else 'No positional args'}")
        logger.info(f"Keyword Arguments: {kwargs if kwargs else 'No keyword args'}")
        
        try:
            result = await func(*args, **kwargs)
            logger.info(f"FUNCTION {func_name} completed successfully")
            logger.info(f"Return value: {result}")
            return result
        except Exception as e:
            logger.error(f"ERROR in function {func_name}: {str(e)}", exc_info=True)
            raise
        finally:
            logger.info(f"EXITING FUNCTION: {func_name}")
            logger.info(f"{'='*50}")
    
    return wrapper

# Load environment variables
load_dotenv(dotenv_path=".env.local")
logger.info("Environment variables loaded from .env.local")

# Log all environment variables (excluding sensitive values)
env_vars = ['MAIL_DEFAULT_SENDER', 'MAIL_DEFAULT_SENDER_NAME', 'AZURE_OPENAI_ENDPOINT']
for var in env_vars:
    value = os.getenv(var)
    logger.info(f"Environment variable {var}: {'[SET]' if value else '[NOT SET]'}")

class AssistantFunction(agents.llm.FunctionContext):
    """This class is used to define functions that will be called by the assistant."""

    @log_function_call
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
        logger.info(f"Image function processing message: {user_msg}")
        return None

    @log_function_call
    @agents.llm.ai_callable(
        description="Send an email to a specified address with the given content and subject"
    )
    async def send_email(
        self,
        to_email: Annotated[str, agents.llm.TypeInfo(description="The email address to send to")],
        body_content: Annotated[str, agents.llm.TypeInfo(description="The content/body of the email")],
        subject: Annotated[str, agents.llm.TypeInfo(description="The subject line of the email")]
    ):
        """Send an email using SendGrid."""
        logger.info(f"Starting email send process to: {to_email}")
        logger.info(f"Subject: {subject}")
        logger.info(f"Body length: {len(body_content)} characters")
        
        try:
            logger.info("Initializing SendGrid client")
            sg = SendGridAPIClient(api_key=os.getenv('SENDGRID_API_KEY'))
            
            logger.info("Creating from_email object")
            from_email = Email(
                email=os.getenv('MAIL_DEFAULT_SENDER'),
                name=os.getenv('MAIL_DEFAULT_SENDER_NAME', 'Appointment System')
            )
            logger.info(f"From email set to: {from_email.email}")
            
            logger.info("Preparing email content")
            content = f"""
            <!DOCTYPE html>
            <html>
            <body>
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                {body_content}
                </div>
            </body>
            </html>
            """
            
            logger.info("Creating Mail object")
            message = Mail(
                from_email=from_email,
                to_emails=To(to_email),
                subject=subject,
                html_content=Content("text/html", content.strip())
            )
            
            logger.info("Preparing to send email")
            def send():
                logger.info("Executing SendGrid send operation")
                response = sg.send(message)
                logger.info(f"SendGrid response status code: {response.status_code}")
                logger.info(f"SendGrid response headers: {response.headers}")
                return response
            
            logger.info("Executing send operation in thread pool")
            await asyncio.get_event_loop().run_in_executor(None, send)
            
            logger.info(f"Email sent successfully to {to_email}")
            return {'status': 'success', 'message': f'Email sent successfully to {to_email}'}
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

@log_function_call
async def get_video_track(room: rtc.Room):
    """Get the first video track from the room."""
    logger.info(f"Searching for video track in room: {room.name}")
    video_track = asyncio.Future[rtc.RemoteVideoTrack]()

    for pid, participant in room.remote_participants.items():
        logger.debug(f"Examining participant {pid}")
        for tid, track_publication in participant.track_publications.items():
            logger.debug(f"Checking track {tid}")
            if track_publication.track is not None and isinstance(
                track_publication.track, rtc.RemoteVideoTrack
            ):
                logger.info(f"Found suitable video track: {track_publication.track.sid}")
                video_track.set_result(track_publication.track)
                break

    return await video_track

@log_function_call
async def entrypoint(ctx: JobContext):
    logger.info("Starting application entrypoint")
    await ctx.connect()
    logger.info(f"Connected to room: {ctx.room.name}")

    logger.info("Initializing chat context")
    chat_context = ChatContext(
        messages=[
            ChatMessage(
                role="system",
                content=(
                    "Your name is Alloy. You are a funny, witty bot. Your interface with users will be voice and vision. "
                    "You can also send emails when requested. When sending emails, make them professional and concise. "
                    "Respond with short and concise answers. Avoid using unpronouncable punctuation or emojis."
                ),
            )
        ]
    )

    logger.info("Initializing Azure GPT")
    azuregpt = openai.LLM.with_azure(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),  
        api_version="2024-08-01-preview",
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        model="gpt-4"
    )

    logger.info("Initializing Google AI")
    google = openai.LLM.with_vertex(model="google/gemini-2.0-flash-exp")

    latest_image: rtc.VideoFrame | None = None

    logger.info("Setting up Voice Assistant")
    assistant = VoiceAssistant(
        vad=silero.VAD.load(),
        stt=deepgram.STT(),
        llm=azuregpt,
        tts=deepgram.TTS(
            model="aura-stella-en",
        ),
        fnc_ctx=AssistantFunction(),
        chat_ctx=chat_context,
    )

    chat = rtc.ChatManager(ctx.room)
    logger.info("Chat manager initialized")

    @log_function_call
    async def _answer(text: str, use_image: bool = False):
        """Generate and deliver response."""
        logger.info(f"Generating answer for text: {text[:100]}...")
        logger.info(f"Using image: {use_image}")
        
        content: list[str | ChatImage] = [text]
        if use_image and latest_image:
            logger.info("Adding image to response")
            content.append(ChatImage(image=latest_image))

        logger.info("Updating chat context")
        chat_context.messages.append(ChatMessage(role="user", content=content))

        logger.info("Generating chat response")
        stream = azuregpt.chat(chat_ctx=chat_context)
        logger.info("Delivering response through assistant")
        await assistant.say(stream, allow_interruptions=True)

    @chat.on("message_received")
    def on_message_received(msg: rtc.ChatMessage):
        """Handle incoming messages."""
        if msg.message:
            logger.info(f"Received message: {msg.message}")
            asyncio.create_task(_answer(msg.message, use_image=False))

    @assistant.on("function_calls_finished")
    def on_function_calls_finished(called_functions: list[agents.llm.CalledFunction]):
        """Handle completed function calls."""
        logger.info(f"Processing {len(called_functions)} completed function calls")
        
        if len(called_functions) == 0:
            return

        for function in called_functions:
            logger.info(f"Processing result from function: {function.name}")
            logger.info(f"Function arguments: {function.call_info.arguments}")
            logger.info(f"Function result: {function.result}")
            
            if function.name == "image":
                user_msg = function.call_info.arguments.get("user_msg")
                if user_msg:
                    logger.info(f"Creating image response task for: {user_msg}")
                    asyncio.create_task(_answer(user_msg, use_image=True))
            elif function.name == "send_email":
                result = function.result
                logger.info(f"Creating email response task with result: {result}")
                asyncio.create_task(_answer(
                    f"Email status: {result.get('status')}. {result.get('message')}", 
                    use_image=False
                ))

    logger.info("Starting assistant")
    assistant.start(ctx.room)

    await asyncio.sleep(1)
    await assistant.say("Hi there! I can help you with vision tasks and sending emails. How can I assist you?", allow_interruptions=True)

    try:
        while ctx.room.connection_state == rtc.ConnectionState.CONN_CONNECTED:
            logger.info("Getting video track")
            video_track = await get_video_track(ctx.room)

            logger.info("Starting video stream processing")
            async for event in rtc.VideoStream(video_track):
                latest_image = event.frame
    except Exception as e:
        logger.error(f"Error in main loop: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    logger.info("="*80)
    logger.info("STARTING APPLICATION")
    logger.info("="*80)
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))