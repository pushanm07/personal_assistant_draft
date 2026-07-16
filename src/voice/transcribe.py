from faster_whisper import WhisperModel

model = WhisperModel("base", device="cpu")

def transcribe_audio():
    segments, _ = model.transcribe(
    "voice.wav",
    language="en",
    vad_filter=False,
    beam_size=5
)
    text = ""
    for segment in segments:
        text += segment.text
    print(text)
    return text


