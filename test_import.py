import sys
sys.path.insert(0, "src")
import app.config
print("config ok")
from app.audio import make_stt, make_tts, make_wake
print("audio ok")
from app.backend import make_client, BackendWorker
print("backend ok")
from app.ui.controller import AppController
print("controller ok")
from app.ui.orb_state import OrbState, STATE_INTENSITY
print("orb states:", [getattr(OrbState, a) for a in dir(OrbState) if not a.startswith("_")])
print("ALL IMPORTS OK")