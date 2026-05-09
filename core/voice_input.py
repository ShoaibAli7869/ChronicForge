"""
core/voice_input.py — faster-whisper STT.
Lazy-loads the tiny model (~75MB, CPU, ~0.5s transcription) on first use.
is_voice_available() checks sounddevice + PortAudio at runtime.
"""

import asyncio
import threading
import traceback
from typing import Callable, Optional

# Check availability
_voice_available = False
_availability_reason = ""
try:
    import sounddevice as sd
    import soundfile as sf

    _voice_available = True
except ImportError:
    _availability_reason = "Missing python packages: sounddevice soundfile"
except OSError as e:
    _availability_reason = f"Missing system dependency (libportaudio2): {e}"

# Lazy model
_whisper_model = None
_on_loading_callback = None
_on_ready_callback = None


def register_loading_callback(
    on_loading: Callable[[], None], on_ready: Callable[[], None]
):
    global _on_loading_callback, _on_ready_callback
    _on_loading_callback = on_loading
    _on_ready_callback = on_ready


def is_voice_available() -> bool:
    return _voice_available


def _load_model():
    global _whisper_model
    if _whisper_model is None:
        try:
            if _on_loading_callback:
                _on_loading_callback()
            from faster_whisper import WhisperModel

            print("[VoiceInput] Loading faster-whisper tiny model (CPU)...")
            _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
            if _on_ready_callback:
                _on_ready_callback()
        except Exception as e:
            print(f"[VoiceInput] Failed to load WhisperModel: {e}")
            raise


class VoiceRecorder:
    def __init__(self, on_transcript=None):
        self.is_recording = False
        self.audio_data = []
        self.stream = None
        self.samplerate = 16000
        self._on_transcript = on_transcript

    def start_recording(self):
        if not _voice_available:
            print("[VoiceInput] Voice not available.")
            return False

        self.is_recording = True
        self.audio_data = []

        def callback(indata, frames, time, status):
            if status:
                print(f"[VoiceInput] Status: {status}")
            self.audio_data.append(indata.copy())

        import sounddevice as sd

        self.stream = sd.InputStream(
            samplerate=self.samplerate, channels=1, callback=callback
        )
        self.stream.start()
        print("[VoiceInput] Started recording...")
        return True

    def stop_and_transcribe_async(self, callback: Callable[[str], None]):
        if not self.is_recording or self.stream is None:
            return

        self.is_recording = False
        self.stream.stop()
        self.stream.close()
        self.stream = None
        print("[VoiceInput] Stopped recording. Transcribing...")

        # Run transcription in a background thread
        thread = threading.Thread(target=self._transcribe_worker, args=(callback,))
        thread.start()

    def _transcribe_worker(self, callback: Callable[[str], None]):
        global _whisper_model
        try:
            _load_model()
            import numpy as np

            if not self.audio_data:
                callback("")
                return

            audio_np = np.concatenate(self.audio_data, axis=0)
            audio_np = audio_np.flatten()

            segments, info = _whisper_model.transcribe(audio_np, beam_size=5)
            text = " ".join([segment.text for segment in segments]).strip()
            print(f"[VoiceInput] Transcription: {text}")
            callback(text)
        except Exception as e:
            print(f"[VoiceInput] Transcription error: {e}")
            traceback.print_exc()
            callback("")
