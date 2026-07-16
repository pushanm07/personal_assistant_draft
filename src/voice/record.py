from email.mime import audio

import sounddevice as sd
import soundfile as sf


def record_voice():
     duration = 5
     samplerate = 16000
     print("Alana's listening...")
     audio = sd.rec(
     int(duration * samplerate),
      samplerate=samplerate,
      channels=1,
      dtype="int16"
    )
     sd.wait()
     sf.write("voice.wav", audio, samplerate)