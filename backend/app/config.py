from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "market_intel"

    nebius_api_key: str = ""
    nebius_base_url: str = "https://api.studio.nebius.ai/v1"
    nebius_model: str = "google/gemma-3-27b-it"

    transcription_provider: str = "sarvam"
    sarvam_api_subscription_key: str = ""
    sarvam_stt_model: str = "saaras:v3"
    sarvam_language_code: str = "unknown"
    sarvam_mode: str = "transcribe"
    sarvam_sample_rate: int = 16000
    sarvam_chunk_seconds: int = 25
    sarvam_parallel_chunks: int = 4
    sarvam_max_retries: int = 2

    whisper_model_size: str = "medium"
    # Use "cpu" on Windows unless CUDA + cuBLAS are fully installed.
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_cpu_threads: int = 4
    whisper_num_workers: int = 2
    reel_audio_max_seconds: int = 0

    check_interval_minutes: int = 5
    historical_reels_limit: int = 100

    download_dir: str = "./downloads"

    instagram_username: str = ""
    instagram_password: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
