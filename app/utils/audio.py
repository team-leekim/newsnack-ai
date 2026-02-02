import io
import os
import uuid
from pydub import AudioSegment

def convert_pcm_to_mp3(pcm_data: bytes, frame_rate: int = 24000) -> bytes:
    audio = AudioSegment(data=pcm_data, sample_width=2, frame_rate=frame_rate, channels=1)
    return audio.export(format="mp3").read()

def get_audio_duration_from_bytes(audio_bytes: bytes, format="mp3") -> float:
    """바이너리 데이터로부터 오디오의 실제 길이를 초 단위로 측정"""
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format=format)
    return len(audio) / 1000.0

def calculate_article_timelines(briefing_segments: list, total_duration: float):
    """
    각 기사 세그먼트의 글자 수 비중을 계산하여 start_time, end_time 할당
    briefing_segments: [{"article_id": 1, "title": "제목", "thumbnail_url": "url", "script": "대본"}, ...]
    """
    # 1. 공백을 제외한 순수 글자 수로 비중 계산
    total_chars = sum(len(segment['script'].replace(" ", "")) for segment in briefing_segments)
    
    current_time = 0.0
    final_briefing_articles = []
    
    for segment in briefing_segments:
        # 2. 글자 수 비중 계산
        pure_script = segment['script'].replace(" ", "")
        char_ratio = len(pure_script) / total_chars if total_chars > 0 else 0
        
        # 3. 해당 세그먼트의 길이 할당
        duration = total_duration * char_ratio
        
        start_time = round(current_time, 2)
        end_time = round(current_time + duration, 2)
        
        # 4. DB 저장용 스펙으로 변환
        final_briefing_articles.append({
            "article_id": segment["article_id"],
            "title": segment["title"],
            "thumbnail_url": segment["thumbnail_url"],
            "start_time": start_time,
            "end_time": end_time
        })
        
        current_time += duration
        
    return final_briefing_articles

def save_local_audio(audio_bytes: bytes) -> str:
    """오디오 로컬 저장 공통 유틸"""
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    file_name = f"{uuid.uuid4().hex}.mp3" 
    file_path = os.path.join(output_dir, file_name)

    with open(file_path, "wb") as f:
        f.write(audio_bytes)
    return file_path
