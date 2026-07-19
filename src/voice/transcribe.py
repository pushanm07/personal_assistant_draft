#import os
#from faster_whisper import WhisperModel

# Initialize model once
#model = WhisperModel("small", device="cpu")

#def transcribe_audio():
    # 1. Double check the file actually exists and has data before running
    if not os.path.exists("voice.wav") or os.path.getsize("voice.wav") == 0:
        print("Error: voice.wav does not exist or is empty!")
        return ""

    # 2. Force a completely flat, non-generator iteration
    try:
        segments, _ = model.transcribe(
            "voice.wav",
            language="en",
            vad_filter=False,             # Disable filter so it cannot accidentally drop audio
            condition_on_previous_text=False,
            beam_size=1
        )
        
        # 3. Pull segments into a list right inside the loop syntax to avoid locks
        text = "".join([segment.text for segment in list(segments)]).strip()
        
        print(f"Result: {text}")
        return text

    except Exception as e:
        print(f"Whisper crashed with error: {e}")
        return ""
