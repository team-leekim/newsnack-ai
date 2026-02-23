import logging

from google.genai import types
from tenacity import retry, stop_after_attempt, wait_random_exponential

from ..providers import ai_factory
from ..prompts import TTS_INSTRUCTIONS, create_tts_prompt
from app.core.config import settings
from app.utils.audio import convert_pcm_to_mp3

logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, min=2, max=10)
)
async def generate_google_audio_task(full_script: str):
    """Google Gemini TTS를 사용한 오디오 생성 태스크 (재시도 포함)"""
    client = ai_factory.get_audio_client()
    prompt = create_tts_prompt(full_script)

    try:
        response = await client.aio.models.generate_content(
            model=settings.GOOGLE_TTS_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=settings.GOOGLE_TTS_VOICE
                        )
                    )
                )
            )
        )

        raw_pcm = response.candidates[0].content.parts[0].inline_data.data
        audio_bytes = convert_pcm_to_mp3(raw_pcm)

        if not audio_bytes:
            raise ValueError("Failed to convert PCM to MP3")

        return audio_bytes

    except Exception as e:
        logger.error(f"Error generating Google audio: {e}")
        raise


@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, min=2, max=10)
)
async def generate_openai_audio_task(full_script: str):
    """OpenAI 전용 오디오 생성 태스크 (재시도 포함)"""
    client = ai_factory.get_audio_client()

    try:
        async with client.audio.speech.with_streaming_response.create(
            model=settings.OPENAI_TTS_MODEL,
            voice=settings.OPENAI_TTS_VOICE,
            input=full_script,
            instructions=TTS_INSTRUCTIONS
        ) as response:
            audio_bytes = await response.read()

        if not audio_bytes:
            raise ValueError("Failed to read audio from OpenAI response")

        return audio_bytes

    except Exception as e:
        logger.error(f"Error generating OpenAI audio: {e}")
        raise
