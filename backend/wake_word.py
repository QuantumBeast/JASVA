"""
wake_word.py — Always-on wake word detection for JASVA.
──────────────────────────────────────────────────────────
Runs a background audio stream via `sounddevice`, feeding frames to Picovoice
Porcupine for offline "Jarvis" (or custom "JASVA") wake word detection.

On detection → evaluates JS in the chat window to start speech recognition
and updates the sphere to its "awakened" state.

Gracefully degrades if Porcupine or audio hardware is unavailable.
"""

import os
import time
import json
import threading
import logging

logger = logging.getLogger("JASVA.wakeword")

# ── Module-level state ──
_wakeword_thread = None
_wakeword_running = False
_wakeword_enabled = True
_last_wake_time = 0
_COOLDOWN_SECONDS = 3  # Prevent rapid re-triggers

# ── Detection callback holder (set by app.pyw) ──
_on_wake_callback = None


def set_wake_callback(callback):
    """Set the function to call when the wake word is detected.
    callback() will be called from the detection thread."""
    global _on_wake_callback
    _on_wake_callback = callback


def _try_porcupine_detection():
    """Primary detection: Picovoice Porcupine offline engine."""
    import pvporcupine
    import sounddevice as sd
    import numpy as np

    global _wakeword_running, _last_wake_time

    # Use built-in "jarvis" keyword (free tier includes it)
    # To use custom "JASVA", train at console.picovoice.ai and pass .ppn path
    access_key = os.environ.get("PICOVOICE_ACCESS_KEY", "")

    # Try to load access key from .env if not in environment
    if not access_key:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        if os.path.exists(env_path):
            try:
                with open(env_path, "r") as f:
                    for line in f:
                        if "=" in line:
                            k, v = line.strip().split("=", 1)
                            if k.strip() == "PICOVOICE_ACCESS_KEY":
                                access_key = v.strip().strip('"').strip("'")
            except Exception:
                pass

    if not access_key:
        raise ValueError(
            "PICOVOICE_ACCESS_KEY not set. Add it to backend/.env or set the "
            "environment variable. Get a free key at https://console.picovoice.ai/"
        )

    # Check for custom .ppn model first, fall back to built-in "jarvis"
    custom_model = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "jasva_wakeword.ppn"
    )
    if os.path.exists(custom_model):
        porcupine = pvporcupine.create(
            access_key=access_key,
            keyword_paths=[custom_model],
            sensitivities=[0.6],
        )
        logger.info("Porcupine loaded with custom 'JASVA' wake word model.")
    else:
        porcupine = pvporcupine.create(
            access_key=access_key,
            keywords=["jarvis"],
            sensitivities=[0.6],
        )
        logger.info("Porcupine loaded with built-in 'Jarvis' wake word.")

    frame_length = porcupine.frame_length
    sample_rate = porcupine.sample_rate

    logger.info(
        f"Wake word engine started: {sample_rate}Hz, {frame_length} samples/frame"
    )

    def _audio_callback(indata, frames, time_info, status):
        global _last_wake_time
        try:
            if not _wakeword_running or not _wakeword_enabled:
                return
            if status:
                logger.debug(f"Audio status: {status}")

            # Convert float32 [-1, 1] to int16
            pcm = (indata[:, 0] * 32767).astype(np.int16)

            # Porcupine needs exactly frame_length samples
            if len(pcm) >= frame_length:
                result = porcupine.process(pcm[:frame_length])
                if result >= 0:
                    now = time.time()
                    if now - _last_wake_time > _COOLDOWN_SECONDS:
                        _last_wake_time = now
                        logger.info("[WAKE] WAKE WORD DETECTED!")
                        if _on_wake_callback:
                            try:
                                _on_wake_callback()
                            except Exception as e:
                                logger.error(f"Wake callback error: {e}")
        except Exception:
            pass

    try:
        with sd.InputStream(
            samplerate=sample_rate,
            blocksize=frame_length,
            channels=1,
            dtype="float32",
            callback=_audio_callback,
        ):
            while _wakeword_running:
                time.sleep(0.1)
    finally:
        porcupine.delete()
        logger.info("Porcupine engine released.")


def _fallback_energy_detection():
    """Fallback: Simple audio energy-based pseudo wake word detection.
    Detects sustained speech-level audio after silence — not a real wake
    word detector, but gives a clap/snap/loud-voice activation feel."""
    import sounddevice as sd
    import numpy as np

    global _wakeword_running, _last_wake_time

    sample_rate = 16000
    frame_duration = 0.03  # 30ms frames
    frame_size = int(sample_rate * frame_duration)
    energy_threshold = 0.02  # RMS threshold for "speech"
    min_active_frames = 8    # ~240ms of sustained audio to trigger
    active_count = 0

    logger.info("Wake word fallback: energy-based detection active (no Porcupine).")

    def _audio_callback(indata, frames, time_info, status):
        nonlocal active_count
        global _last_wake_time
        try:
            if not _wakeword_running or not _wakeword_enabled:
                return

            rms = np.sqrt(np.mean(indata[:, 0] ** 2))
            if rms > energy_threshold:
                active_count += 1
                if active_count >= min_active_frames:
                    now = time.time()
                    if now - _last_wake_time > _COOLDOWN_SECONDS:
                        _last_wake_time = now
                        active_count = 0
                        logger.info("[WAKE] ENERGY WAKE DETECTED (fallback)!")
                        if _on_wake_callback:
                            try:
                                _on_wake_callback()
                            except Exception as e:
                                logger.error(f"Wake callback error: {e}")
            else:
                active_count = max(0, active_count - 1)
        except Exception:
            pass

    try:
        with sd.InputStream(
            samplerate=sample_rate,
            blocksize=frame_size,
            channels=1,
            dtype="float32",
            callback=_audio_callback,
        ):
            while _wakeword_running:
                time.sleep(0.1)
    except Exception as e:
        logger.error(f"Fallback energy detection error: {e}")


def _detection_loop():
    """Main detection loop — tries Porcupine, falls back to energy detection."""
    global _wakeword_running
    try:
        _try_porcupine_detection()
    except Exception as e:
        logger.warning(f"Porcupine not available ({e}), using energy fallback.")
        try:
            _fallback_energy_detection()
        except Exception as e2:
            logger.error(f"All wake word detection failed: {e2}")
    _wakeword_running = False


def start_wake_word(callback=None):
    """Start the background wake word detection thread.
    
    Args:
        callback: Function to call when the wake word is detected.
                  Called from the detection thread — should be thread-safe.
    """
    global _wakeword_thread, _wakeword_running
    if _wakeword_running:
        logger.debug("Wake word already running.")
        return
    if callback:
        set_wake_callback(callback)
    _wakeword_running = True
    _wakeword_thread = threading.Thread(target=_detection_loop, daemon=True)
    _wakeword_thread.start()
    logger.info("Wake word detection thread started.")


def stop_wake_word():
    """Stop the background wake word detection."""
    global _wakeword_running
    _wakeword_running = False
    logger.info("Wake word detection stopped.")


def set_wake_word_enabled(enabled):
    """Enable or disable wake word detection without stopping the audio stream."""
    global _wakeword_enabled
    _wakeword_enabled = bool(enabled)
    logger.info(f"Wake word {'enabled' if _wakeword_enabled else 'disabled'}.")


def is_wake_word_running():
    """Check if the wake word detection thread is active."""
    return _wakeword_running


def get_wake_word_status():
    """Return the current status of the wake word engine."""
    return {
        "running": _wakeword_running,
        "enabled": _wakeword_enabled,
        "last_wake_time": _last_wake_time,
    }
