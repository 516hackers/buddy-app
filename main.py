import json
import math
import os
import re
import subprocess
import threading
import time
from collections import deque
from datetime import datetime
from typing import Tuple

# ── Kivy – MUST come before Window import ────────────────────────────────
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.graphics import (Color, Ellipse, Line, Rectangle, RoundedRectangle)
from kivy.metrics import dp
from kivy.properties import NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

# ── Platform detection ────────────────────────────────────────────────────
def _detect_android() -> bool:
    try:
        import platform
        if platform.system() != "Linux":
            return False
        with open("/proc/version", "r") as f:
            return "android" in f.read().lower()
    except Exception:
        return False

ON_ANDROID = _detect_android()

# ── Android Native Speech Recognition ─────────────────────────────────────
ANDROID_SPEECH_OK = False
_android_recognizer = None
_PythonActivity = None
_activity = None

def init_android_speech():
    """Initialize Android's native speech recognizer"""
    global ANDROID_SPEECH_OK, _android_recognizer, _PythonActivity, _activity
    
    if not ON_ANDROID:
        return False
    
    try:
        from jnius import autoclass, PythonJavaClass, java_method
        from android.runnable import run_on_ui_thread
        
        _PythonActivity = autoclass("org.kivy.android.PythonActivity")
        _activity = _PythonActivity.mActivity
        
        # SpeechRecognizer class
        SpeechRecognizer = autoclass("android.speech.SpeechRecognizer")
        RecognizerIntent = autoclass("android.speech.RecognizerIntent")
        
        # Create the recognizer
        _android_recognizer = SpeechRecognizer.createSpeechRecognizer(_activity)
        
        # Create a listener class
        class RecognitionListener(PythonJavaClass):
            __javainterfaces__ = ["android/speech/RecognitionListener"]
            
            def __init__(self, callback):
                super().__init__()
                self.callback = callback
                self.results = []
            
            @java_method('(I)V')
            def onReadyForSpeech(self, params):
                pass
            
            @java_method('(I)V')
            def onBeginningOfSpeech(self):
                pass
            
            @java_method('(I)V')
            def onRmsChanged(self, rmsdB):
                pass
            
            @java_method('(I)V')
            def onBufferReceived(self, buffer):
                pass
            
            @java_method('(I)V')
            def onEndOfSpeech(self):
                pass
            
            @java_method('(I)V')
            def onError(self, error):
                if self.callback:
                    self.callback("", error)
            
            @java_method('(Landroid/os/Bundle;)V')
            def onResults(self, results):
                if self.callback:
                    matches = results.getStringArrayList(
                        autoclass("android.speech.SpeechRecognizer").RESULTS_RECOGNITION
                    )
                    if matches and matches.size() > 0:
                        self.callback(str(matches.get(0)), None)
                    else:
                        self.callback("", None)
            
            @java_method('(Landroid/os/Bundle;)V')
            def onPartialResults(self, partialResults):
                pass
            
            @java_method('(I)V')
            def onEvent(self, eventType, params):
                pass
        
        # Store the listener class for later use
        _android_recognizer.RecognitionListener = RecognitionListener
        ANDROID_SPEECH_OK = True
        return True
        
    except Exception as e:
        print(f"Failed to init Android speech: {e}")
        ANDROID_SPEECH_OK = False
        return False

def start_android_speech_listening(callback):
    """Start listening using Android's native speech recognizer"""
    global _android_recognizer, _activity
    
    if not ANDROID_SPEECH_OK or not _android_recognizer:
        if callback:
            callback("", "Speech recognizer not available")
        return
    
    try:
        from jnius import autoclass
        
        RecognizerIntent = autoclass("android.speech.RecognizerIntent")
        intent = RecognizerIntent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, 
                        RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        intent.putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, 
                        _activity.getPackageName())
        intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, True)
        intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        
        # Create listener
        listener = _android_recognizer.RecognitionListener(callback)
        
        # Start listening
        _android_recognizer.setRecognitionListener(listener)
        _android_recognizer.startListening(intent)
        
    except Exception as e:
        print(f"Error starting speech recognition: {e}")
        if callback:
            callback("", str(e))

# ── TTS globals ──────────────────────────────────────────────────────────
TTS_OK       = False
_tts_lock    = threading.Lock()
_android_tts = None
_desktop_tts = None

def _init_android_tts():
    """Initialise Android TextToSpeech via pyjnius"""
    global _android_tts, TTS_OK
    if not ON_ANDROID:
        return
    try:
        from jnius import autoclass, PythonJavaClass, java_method
        
        TextToSpeech = autoclass("android.speech.tts.TextToSpeech")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        context = PythonActivity.mActivity
        
        class TTSInitListener(PythonJavaClass):
            __javainterfaces__ = ["android/speech/tts/TextToSpeech$OnInitListener"]
            
            def __init__(self):
                super().__init__()
                self.ready = False
            
            @java_method("(I)V")
            def onInit(self, status):
                global TTS_OK
                TTS_OK = (status == 0)
                self.ready = True
        
        listener = TTSInitListener()
        _android_tts = TextToSpeech(context, listener)
    except Exception as e:
        print(f"TTS init error: {e}")
        TTS_OK = False

def _init_desktop_tts():
    """Desktop-only fallback"""
    global _desktop_tts, TTS_OK
    if ON_ANDROID:
        return
    try:
        import pyttsx3
        _desktop_tts = pyttsx3.init()
        _desktop_tts.setProperty("rate", 165)
        TTS_OK = True
    except Exception:
        TTS_OK = False

def speak_tts(text: str, enabled: bool):
    """Non-blocking TTS"""
    if not enabled or not text:
        return
    
    def _speak():
        with _tts_lock:
            if ON_ANDROID:
                if _android_tts is None:
                    return
                try:
                    from jnius import autoclass
                    TTS = autoclass("android.speech.tts.TextToSpeech")
                    _android_tts.speak(text, TTS.QUEUE_FLUSH, None, "buddy_utt")
                except Exception:
                    pass
            else:
                if _desktop_tts is not None:
                    try:
                        _desktop_tts.say(text)
                        _desktop_tts.runAndWait()
                    except Exception:
                        pass
    
    threading.Thread(target=_speak, daemon=True).start()

# ── Palette ───────────────────────────────────────────────────────────────
CARD   = (0.09, 0.09, 0.13, 1)
SURF   = (0.13, 0.13, 0.18, 1)
ACCENT = (0.42, 0.38, 1.00, 1)
GREEN  = (0.20, 0.85, 0.45, 1)
AMBER  = (1.00, 0.72, 0.10, 1)
RED    = (1.00, 0.32, 0.32, 1)
DIM    = (0.28, 0.28, 0.40, 1)
SEC    = (0.55, 0.55, 0.68, 1)
PRI    = (0.92, 0.92, 0.96, 1)
BORDER = (0.18, 0.18, 0.26, 1)

# ── Constants ─────────────────────────────────────────────────────────────
WAKE_WORD      = "hello buddy"
CONV_TIMEOUT   = 30
MAX_LOG_LINES  = 50

# ── Paths ─────────────────────────────────────────────────────────────────
SETTINGS_FILE = ""
LOG_FILE      = ""

def _init_paths():
    """Called from App.build() after Android storage is ready"""
    global SETTINGS_FILE, LOG_FILE
    try:
        if ON_ANDROID:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            ctx = PythonActivity.mActivity
            fdir = ctx.getFilesDir().getAbsolutePath()
            data_dir = os.path.join(fdir, "buddy_assistant")
        else:
            data_dir = os.path.expanduser("~/.buddy_assistant")
        os.makedirs(data_dir, exist_ok=True)
        SETTINGS_FILE = os.path.join(data_dir, "settings.json")
        LOG_FILE = os.path.join(data_dir, "activity.log")
    except Exception:
        SETTINGS_FILE = "settings.json"
        LOG_FILE = "activity.log"

# ── App intent map ────────────────────────────────────────────────────────
APP_MAP = {
    "whatsapp":   ("com.whatsapp", "com.whatsapp/.Main"),
    "youtube":    ("com.google.android.youtube", "com.google.android.youtube/.HomeActivity"),
    "chrome":     ("com.android.chrome", "com.android.chrome/com.google.android.apps.chrome.Main"),
    "phone":      ("com.android.dialer", None),
    "camera":     ("android.media.action.IMAGE_CAPTURE", None),
    "settings":   ("com.android.settings", "com.android.settings/.Settings"),
    "maps":       ("com.google.android.apps.maps", "com.google.android.apps.maps/.MapsActivity"),
    "spotify":    ("com.spotify.music", "com.spotify.music/.MainActivity"),
    "telegram":   ("org.telegram.messenger", "org.telegram.messenger/.DefaultIcon"),
    "gmail":      ("com.google.android.gm", "com.google.android.gm/.ConversationListActivityGmail"),
    "calculator": ("com.android.calculator2", "com.android.calculator2/.Calculator"),
    "gallery":    ("com.google.android.apps.photos", "com.google.android.apps.photos/.home.HomeActivity"),
    "contacts":   ("com.android.contacts", "com.android.contacts/.activities.PeopleActivity"),
    "clock":      ("com.android.deskclock", "com.android.deskclock/.DeskClock"),
    "files":      ("com.google.android.documentsui", "com.google.android.documentsui/.files.FilesActivity"),
}

# ── Intent regexes ────────────────────────────────────────────────────────
INTENT_OPEN   = re.compile(r"open\s+(.+)")
INTENT_SEARCH = re.compile(r"(?:search|google|find|look up)\s+(.+)")
INTENT_ALARM  = re.compile(r"(?:set\s+)?alarm\s+(?:for\s+)?(.+)")
INTENT_TIMER  = re.compile(r"(?:set\s+)?timer\s+(?:for\s+)?(\d+)\s*(second|minute|hour)s?")
INTENT_VOL_UP = re.compile(r"volume\s+up|louder|increase\s+volume")
INTENT_VOL_DN = re.compile(r"volume\s+down|quieter|lower\s+volume|decrease\s+volume")
INTENT_MUTE   = re.compile(r"\bmute\b")
INTENT_TORCH  = re.compile(r"(?:turn\s+)?(?:on|off|toggle)\s+(?:torch|flashlight|flash)")
INTENT_TIME   = re.compile(r"(?:what(?:'s|\s+is)\s+)?(?:the\s+)?time")
INTENT_DATE   = re.compile(r"(?:what(?:'s|\s+is)\s+)?(?:the\s+)?date|what\s+day")
INTENT_BATT   = re.compile(r"battery|power\s+level")
INTENT_STOP   = re.compile(r"\b(?:stop|sleep|bye|goodbye|exit)\b")
INTENT_HELP   = re.compile(r"\bhelp\b|\bwhat\s+can\s+you\s+do\b|\bcommands\b")

# ── Settings ─────────────────────────────────────────────────────────────
_DEFAULTS = {
    "tts_enabled": True,
    "conv_mode": True,
    "custom_cmds": {},
    "log_to_file": True,
}

def load_settings() -> dict:
    try:
        with open(SETTINGS_FILE) as f:
            data = json.load(f)
        merged = dict(_DEFAULTS)
        merged.update(data)
        return merged
    except Exception:
        return dict(_DEFAULTS)

def save_settings(s: dict):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(s, f, indent=2)
    except Exception:
        pass

# ════════════════════════════════════════════════════════════════
#  ANDROID SYSTEM HELPERS
# ════════════════════════════════════════════════════════════════
def _am(*args) -> bool:
    try:
        r = subprocess.run(
            ["am"] + list(args),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5
        )
        return r.returncode == 0
    except Exception:
        return False

def launch_app(name: str) -> Tuple[bool, str]:
    key = name.lower().strip()
    for trigger, (pkg, activity) in APP_MAP.items():
        if trigger in key or key in trigger:
            if activity:
                if _am("start", "-n", activity):
                    return True, f"Opening {trigger.capitalize()}"
            if _am("start", "-n", f"{pkg}/.MainActivity"):
                return True, f"Opening {trigger.capitalize()}"
            _am("start", "-a", "android.intent.action.VIEW",
                "-d", f"market://details?id={pkg}")
            return False, f"{trigger.capitalize()} not installed"
    return False, f"No app found for '{name}'"

def web_search(query: str) -> Tuple[bool, str]:
    url = "https://www.google.com/search?q=" + query.replace(" ", "+")
    ok = _am("start", "-a", "android.intent.action.VIEW", "-d", url)
    return ok, f"Searching: {query}"

def set_alarm(time_str: str) -> Tuple[bool, str]:
    ok = _am("start", "-a", "android.intent.action.SET_ALARM",
             "--ez", "android.intent.extra.alarm.SKIP_UI", "false",
             "--es", "android.intent.extra.alarm.MESSAGE", "Buddy Alarm")
    return ok, f"Setting alarm for {time_str}"

def set_timer(seconds: int) -> Tuple[bool, str]:
    ok = _am("start", "-a", "android.intent.action.SET_TIMER",
             "--ei", "android.intent.extra.alarm.LENGTH", str(seconds),
             "--ez", "android.intent.extra.alarm.SKIP_UI", "false")
    return ok, f"Timer set for {seconds}s"

def toggle_torch() -> Tuple[bool, str]:
    try:
        subprocess.run(
            ["settings", "put", "system", "torch_state", "1"],
            timeout=3, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    except Exception:
        pass
    return True, "Toggling flashlight"

def get_battery() -> str:
    try:
        out = subprocess.check_output(
            ["dumpsys", "battery"], timeout=4, stderr=subprocess.DEVNULL
        ).decode()
        level = re.search(r"level:\s*(\d+)", out)
        status = re.search(r"status:\s*(\d+)", out)
        pct = level.group(1) if level else "?"
        charging = status and status.group(1) == "2"
        return f"Battery: {pct}%{'  (charging)' if charging else ''}"
    except Exception:
        return "Battery: unavailable"

# ════════════════════════════════════════════════════════════════
#  INTENT ENGINE
# ════════════════════════════════════════════════════════════════
def parse_intent(text: str) -> Tuple[str, str]:
    t = text.lower().strip()
    if INTENT_STOP.search(t):   return "stop",    ""
    if INTENT_HELP.search(t):   return "help",    ""
    if INTENT_TIME.search(t) and not INTENT_ALARM.search(t):
                                 return "time",    ""
    if INTENT_DATE.search(t):   return "date",    ""
    if INTENT_BATT.search(t):   return "battery", ""
    if INTENT_VOL_UP.search(t): return "vol_up",  ""
    if INTENT_VOL_DN.search(t): return "vol_down",""
    if INTENT_MUTE.search(t):   return "mute",    ""
    if INTENT_TORCH.search(t):  return "torch",   ""
    m = INTENT_TIMER.search(t)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        secs = n * (60 if unit == "minute" else 3600 if unit == "hour" else 1)
        return "timer", str(secs)
    m = INTENT_ALARM.search(t)
    if m: return "alarm",    m.group(1).strip()
    m = INTENT_SEARCH.search(t)
    if m: return "search",   m.group(1).strip()
    m = INTENT_OPEN.search(t)
    if m: return "open_app", m.group(1).strip()
    for trigger in APP_MAP:
        if trigger in t:
            return "open_app", trigger
    return "unknown", t

# ════════════════════════════════════════════════════════════════
#  UI WIDGETS
# ════════════════════════════════════════════════════════════════

class Card(BoxLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.orientation = "vertical"
        self.padding = [dp(16), dp(12), dp(16), dp(12)]
        self.spacing = dp(6)
        with self.canvas.before:
            Color(*CARD)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])
            Color(*BORDER)
            self._bd = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, dp(14)),
                width=dp(0.8)
            )
        self.bind(pos=self._upd, size=self._upd)
    
    def _upd(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._bd.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(14))

class Toggle(Widget):
    """Animated on/off toggle"""
    _prog = NumericProperty(0.0)
    
    W = dp(54)
    H = dp(28)
    
    def __init__(self, callback=None, **kw):
        super().__init__(size_hint=(None, None), size=(self.W, self.H), **kw)
        self._on = False
        self._cb = callback
        self._anim = None
        self.bind(_prog=lambda *_: self._draw())
        self._draw()
        self.bind(on_touch_up=self._touch)
    
    def set_state(self, val, silent=False):
        if val == self._on:
            return
        self._on = val
        if not silent and self._cb:
            self._cb(val)
        self._run_anim()
    
    @property
    def is_on(self):
        return self._on
    
    def _touch(self, _, touch):
        if self.collide_point(*touch.pos):
            self._on = not self._on
            if self._cb:
                self._cb(self._on)
            self._run_anim()
        return False
    
    def _run_anim(self):
        if self._anim:
            self._anim.cancel(self)
        target = 1.0 if self._on else 0.0
        self._anim = Animation(_prog=target, duration=0.18)
        self._anim.start(self)
    
    def _draw(self, *_):
        self.canvas.clear()
        t = self._prog
        r = 0.18 + t * (0.42 - 0.18)
        g = 0.18 + t * (0.38 - 0.18)
        b = 0.26 + t * (1.00 - 0.26)
        W, H = self.width, self.height
        with self.canvas:
            Color(r, g, b, 1)
            RoundedRectangle(pos=self.pos, size=(W, H), radius=[H / 2])
            travel = W - H
            cx = self.x + H / 2 + t * travel
            cy = self.y + H / 2
            R = H / 2 - dp(3)
            Color(0.95, 0.95, 0.97, 1)
            Ellipse(pos=(cx - R, cy - R), size=(R * 2, R * 2))

class Toast(Popup):
    def __init__(self, msg, color=ACCENT, dur=2.8, **kw):
        row = BoxLayout(orientation="horizontal",
                        padding=[dp(14), dp(10)], spacing=dp(10))
        with row.canvas.before:
            Color(*CARD)
            self._bg = RoundedRectangle(radius=[dp(14)])
        row.bind(pos=lambda w, v: setattr(self._bg, "pos", v),
                 size=lambda w, v: setattr(self._bg, "size", v))
        row.add_widget(Label(text="◉", font_size=dp(18), color=color,
                             size_hint=(None, 1), width=dp(28)))
        row.add_widget(Label(text=msg, font_size=dp(13), color=PRI, bold=True,
                             text_size=(dp(220), None),
                             halign="left", valign="middle"))
        super().__init__(
            title="", content=row,
            size_hint=(None, None), size=(dp(270), dp(68)),
            separator_height=0,
            background="", background_color=(0, 0, 0, 0), **kw
        )
        Clock.schedule_once(lambda dt: self.dismiss(), dur)

class WaveViz(Widget):
    """Animated bar visualiser"""
    BARS = 16
    BAR_W = dp(3)
    GAP = dp(3)
    
    def __init__(self, **kw):
        super().__init__(size_hint=(1, None), height=dp(60), **kw)
        self._phase = 0.0
        self._running = False
        self._ev = None
        self._levels = [0.1] * self.BARS
        self._draw_idle()
    
    def start(self):
        if self._running:
            return
        self._running = True
        self._ev = Clock.schedule_interval(self._tick, 1 / 24)
    
    def stop(self):
        self._running = False
        if self._ev:
            self._ev.cancel()
            self._ev = None
        self._draw_idle()
    
    def feed(self, amplitude: float):
        import random
        for i in range(self.BARS):
            self._levels[i] = max(0.05, min(1.0, amplitude + random.uniform(-0.15, 0.15)))
    
    def _draw_idle(self):
        self.canvas.clear()
        cx = self.center_x
        total = self.BARS * (self.BAR_W + self.GAP) - self.GAP
        x0 = cx - total / 2
        with self.canvas:
            for i in range(self.BARS):
                Color(*DIM, 0.5)
                h = dp(4)
                x = x0 + i * (self.BAR_W + self.GAP)
                y = self.center_y - h / 2
                RoundedRectangle(pos=(x, y), size=(self.BAR_W, h), radius=[self.BAR_W / 2])
    
    def _tick(self, dt):
        self._phase += 0.14
        self.canvas.clear()
        cx = self.center_x
        max_h = self.height * 0.85
        total = self.BARS * (self.BAR_W + self.GAP) - self.GAP
        x0 = cx - total / 2
        with self.canvas:
            for i in range(self.BARS):
                wave = 0.5 + 0.5 * math.sin(self._phase + i * 0.45)
                h = max(dp(4), max_h * self._levels[i] * wave)
                x = x0 + i * (self.BAR_W + self.GAP)
                y = self.center_y - h / 2
                t2 = i / max(1, self.BARS - 1)
                r = 0.42 + t2 * (0.20 - 0.42)
                g = 0.38 + t2 * (0.85 - 0.38)
                b = 1.00 + t2 * (0.45 - 1.00)
                Color(r, g, b, 0.85)
                RoundedRectangle(pos=(x, y), size=(self.BAR_W, h), radius=[self.BAR_W / 2])

# ════════════════════════════════════════════════════════════════
#  MAIN UI
# ════════════════════════════════════════════════════════════════
class BuddyUI(FloatLayout):
    
    def __init__(self, **kw):
        super().__init__(**kw)
        self._settings = load_settings()
        self._active = False
        self._waiting = False
        self._conv_deadline = 0.0
        self._listening_for_wake = True
        self._log_lines = deque(maxlen=MAX_LOG_LINES)
        self._speech_callback = None
        self._build()
        
        # Initialize speech recognition on Android
        if ON_ANDROID:
            init_android_speech()
            if ANDROID_SPEECH_OK:
                self._write_log("Android speech recognition initialized")
            else:
                self._write_log("Android speech not available - using text input mode")
                self._add_text_input_mode()
        else:
            self._write_log("Desktop mode - using text input")
            self._add_text_input_mode()
    
    # ── Build ─────────────────────────────────────────────────────────────
    def _build(self):
        sv = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        root = BoxLayout(
            orientation="vertical",
            padding=[dp(16), dp(8), dp(16), dp(24)],
            spacing=dp(10),
            size_hint_y=None
        )
        root.bind(minimum_height=root.setter("height"))
        
        # top bar
        bar = BoxLayout(size_hint_y=None, height=dp(24))
        bar.add_widget(Label(text="Buddy Assistant", font_size=dp(10),
                             color=SEC, halign="left"))
        bar.add_widget(Label(text="v3.0", font_size=dp(10),
                             color=DIM, halign="right"))
        root.add_widget(bar)
        
        # title
        hdr = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(4))
        hdr.add_widget(Label(text="[b]Buddy[/b]", markup=True,
                             font_size=dp(26), color=PRI,
                             size_hint_x=None, width=dp(90), halign="left"))
        hdr.add_widget(Label(text="Assistant", font_size=dp(26),
                             color=ACCENT, halign="left"))
        root.add_widget(hdr)
        
        root.add_widget(Label(
            text="Voice-controlled AI companion",
            font_size=dp(11), color=SEC,
            size_hint_y=None, height=dp(18), halign="left"
        ))
        root.add_widget(self._divider())
        
        # status card
        sc = Card(size_hint_y=None, height=dp(86))
        srow = BoxLayout(size_hint_y=None, height=dp(20))
        srow.add_widget(Label(text="Status", font_size=dp(10), color=SEC,
                              halign="left"))
        self._dot = Label(text="●", font_size=dp(14), color=DIM,
                          size_hint_x=None, width=dp(26), halign="right")
        srow.add_widget(self._dot)
        self._stat = Label(text="Inactive", font_size=dp(18),
                           bold=True, color=DIM,
                           halign="left", size_hint_y=None, height=dp(34))
        self._sub = Label(text="Toggle Active to begin",
                           font_size=dp(10), color=SEC,
                           halign="left", size_hint_y=None, height=dp(18))
        sc.add_widget(srow)
        sc.add_widget(self._stat)
        sc.add_widget(self._sub)
        root.add_widget(sc)
        
        # toggle card
        tc = Card(size_hint_y=None, height=dp(100))
        self._tog_active = Toggle(callback=self._on_active_tap)
        self._tog_inactive = Toggle(callback=self._on_inactive_tap)
        self._tog_inactive.set_state(True, silent=True)
        tc.add_widget(self._row_toggle(self._tog_active,
                                       "Active  [Listen]",
                                       "Tap to start listening"))
        tc.add_widget(Widget(size_hint_y=None, height=dp(4)))
        tc.add_widget(self._row_toggle(self._tog_inactive,
                                       "Inactive  [Sleep]",
                                       "Buddy sleeps"))
        root.add_widget(tc)
        
        # wave + hint
        self._wave = WaveViz()
        root.add_widget(self._wave)
        self._hint = Label(
            text='Say  "Hello Buddy"  to wake up',
            font_size=dp(11), color=DIM,
            size_hint_y=None, height=dp(20)
        )
        root.add_widget(self._hint)
        
        # settings card
        root.add_widget(self._build_settings_card())
        
        # log card
        lc = Card(size_hint_y=None, height=dp(180))
        lhdr = BoxLayout(size_hint_y=None, height=dp(22))
        lhdr.add_widget(Label(text="Activity Log", font_size=dp(10),
                              color=SEC, halign="left"))
        clr = Button(text="Clear", font_size=dp(10),
                     background_normal="", background_color=SURF, color=SEC,
                     size_hint=(None, None), size=(dp(48), dp(22)))
        clr.bind(on_release=self._clear_log)
        lhdr.add_widget(clr)
        lc.add_widget(lhdr)
        self._log_lbl = Label(
            text="Ready — toggle Active to begin.",
            font_size=dp(10), color=SEC,
            halign="left", valign="top",
            text_size=(Window.width - dp(56), None)
        )
        lc.add_widget(self._log_lbl)
        root.add_widget(lc)
        
        # quick test
        root.add_widget(self._build_quick_test())
        
        # custom cmd
        root.add_widget(self._build_custom_cmd())
        
        # help
        root.add_widget(self._build_help())
        
        root.add_widget(Label(text="Buddy v3.0", font_size=dp(9),
                              color=DIM, size_hint_y=None, height=dp(28)))
        
        sv.add_widget(root)
        self.add_widget(sv)
    
    # ── Widget helpers ────────────────────────────────────────────────────
    def _divider(self):
        d = Widget(size_hint_y=None, height=dp(1))
        with d.canvas:
            Color(*BORDER)
            rect = Rectangle(pos=d.pos, size=d.size)
        d.bind(pos=lambda w, v: setattr(rect, "pos", v),
               size=lambda w, v: setattr(rect, "size", v))
        return d
    
    def _row_toggle(self, tog, title, sub):
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(10))
        col = BoxLayout(orientation="vertical", spacing=dp(2))
        col.add_widget(Label(text=title, font_size=dp(13), bold=True,
                             color=PRI, halign="left"))
        col.add_widget(Label(text=sub, font_size=dp(9), color=SEC,
                             halign="left"))
        row.add_widget(col)
        row.add_widget(tog)
        return row
    
    def _build_settings_card(self):
        card = Card(size_hint_y=None, height=dp(140))
        card.add_widget(Label(text="Settings", font_size=dp(10), color=SEC,
                              size_hint_y=None, height=dp(18), halign="left"))
        
        # tts toggle
        tr = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        tr.add_widget(Label(text="TTS Voice Feedback", font_size=dp(11),
                            color=PRI, halign="left"))
        self._tog_tts = Toggle(callback=lambda v: self._settings.update({"tts_enabled": v}))
        self._tog_tts.set_state(self._settings["tts_enabled"], silent=True)
        tr.add_widget(self._tog_tts)
        card.add_widget(tr)
        
        # conv mode
        cr = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        cr.add_widget(Label(text="Conversation Mode (30s)", font_size=dp(11),
                            color=PRI, halign="left"))
        self._tog_conv = Toggle(callback=lambda v: self._settings.update({"conv_mode": v}))
        self._tog_conv.set_state(self._settings["conv_mode"], silent=True)
        cr.add_widget(self._tog_conv)
        card.add_widget(cr)
        
        sb = Button(text="Save Settings", font_size=dp(12),
                    background_normal="", background_color=ACCENT,
                    color=PRI, bold=True,
                    size_hint_y=None, height=dp(34))
        sb.bind(on_release=self._save_settings)
        card.add_widget(sb)
        return card
    
    def _build_quick_test(self):
        card = Card(size_hint_y=None, height=dp(200))
        card.add_widget(Label(text="Quick Test  (type or speak)",
                              font_size=dp(10), color=SEC,
                              size_hint_y=None, height=dp(18), halign="left"))
        tests = [
            ("Wake word", WAKE_WORD),
            ("Open YouTube", "open youtube"),
            ("Search AI news", "search artificial intelligence"),
            ("Battery level", "battery"),
            ("Current time", "what time is it"),
            ("Timer 1 minute", "set timer for 1 minute"),
        ]
        for label, cmd in tests:
            btn = Button(text=label, font_size=dp(11),
                         background_normal="", background_color=SURF,
                         color=ACCENT, bold=True,
                         size_hint_y=None, height=dp(28))
            btn.bind(on_release=lambda _, c=cmd: self._process(c))
            card.add_widget(btn)
        return card
    
    def _build_custom_cmd(self):
        card = Card(size_hint_y=None, height=dp(144))
        card.add_widget(Label(text="Custom Command",
                              font_size=dp(10), color=SEC,
                              size_hint_y=None, height=dp(18), halign="left"))
        card.add_widget(Label(text="phrase  →  Android package",
                              font_size=dp(9), color=DIM,
                              size_hint_y=None, height=dp(14), halign="left"))
        self._cc_phrase = TextInput(
            hint_text="Trigger phrase  e.g. open netflix",
            font_size=dp(12), background_color=SURF, foreground_color=PRI,
            size_hint_y=None, height=dp(34), multiline=False,
            use_bubble=False, write_tab=False
        )
        self._cc_pkg = TextInput(
            hint_text="Package  e.g. com.netflix.mediaclient",
            font_size=dp(12), background_color=SURF, foreground_color=PRI,
            size_hint_y=None, height=dp(34), multiline=False,
            use_bubble=False, write_tab=False
        )
        add = Button(text="Add Command", font_size=dp(12),
                     background_normal="", background_color=GREEN,
                     color=(0, 0, 0, 1), bold=True,
                     size_hint_y=None, height=dp(30))
        add.bind(on_release=self._add_custom_cmd)
        card.add_widget(self._cc_phrase)
        card.add_widget(self._cc_pkg)
        card.add_widget(add)
        return card
    
    def _build_help(self):
        card = Card(size_hint_y=None, height=dp(258))
        card.add_widget(Label(text="Voice Commands",
                              font_size=dp(10), color=SEC,
                              size_hint_y=None, height=dp(18), halign="left"))
        cmds = [
            ("Hello Buddy", "Wake word"),
            ("Open <app>", "Launch any app"),
            ("Search <query>", "Google search"),
            ("Set alarm for 7am", "Alarm dialog"),
            ("Set timer for 5 minutes", "Countdown"),
            ("Volume up / down", "Media volume"),
            ("Mute", "Mute device"),
            ("Toggle torch", "Flashlight"),
            ("What time is it", "Current time"),
            ("What is the date", "Today's date"),
            ("Battery", "Battery level"),
            ("Help", "Show commands"),
            ("Stop / Goodbye", "Deactivate"),
        ]
        for phrase, desc in cmds:
            row = BoxLayout(size_hint_y=None, height=dp(17))
            row.add_widget(Label(text=phrase, font_size=dp(10),
                                 color=ACCENT, halign="left",
                                 size_hint_x=0.58))
            row.add_widget(Label(text=desc, font_size=dp(10),
                                 color=SEC, halign="left",
                                 size_hint_x=0.42))
            card.add_widget(row)
        return card
    
    def _add_text_input_mode(self):
        """Add text input for manual commands when speech isn't available"""
        # Create container for text input
        input_container = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(50),
            padding=[dp(10), dp(5)],
            spacing=dp(8)
        )
        
        with input_container.canvas.before:
            Color(*CARD)
            self._input_bg = RoundedRectangle(pos=input_container.pos, 
                                              size=input_container.size, 
                                              radius=[dp(12)])
        input_container.bind(pos=self._update_input_bg, size=self._update_input_bg)
        
        # Text input
        self._text_input = TextInput(
            hint_text="Type command here (speech not available)",
            font_size=dp(12),
            background_color=SURF,
            foreground_color=PRI,
            size_hint_x=0.8,
            multiline=False,
            write_tab=False,
            use_bubble=False
        )
        self._text_input.bind(on_text_validate=self._on_text_command)
        
        # Send button
        send_btn = Button(
            text="SEND",
            font_size=dp(11),
            background_normal="",
            background_color=ACCENT,
            color=PRI,
            bold=True,
            size_hint_x=0.2,
            size_hint_y=None,
            height=dp(40)
        )
        send_btn.bind(on_release=lambda x: self._on_text_command(self._text_input))
        
        input_container.add_widget(self._text_input)
        input_container.add_widget(send_btn)
        
        # Add to main layout - find the ScrollView and add after wave
        self.add_widget(input_container)
        self._text_input_container = input_container
        
        self._write_log("Text input mode enabled - type commands directly")
    
    def _update_input_bg(self, instance, value):
        if hasattr(self, '_input_bg'):
            self._input_bg.pos = instance.pos
            self._input_bg.size = instance.size
    
    def _on_text_command(self, text_input):
        """Handle text input commands"""
        cmd = text_input.text.strip().lower()
        if cmd:
            self._write_log(f'Text command: "{cmd}"')
            self._process(cmd)
            text_input.text = ""
    
    # ── Settings callbacks ────────────────────────────────────────────────
    def _save_settings(self, *_):
        save_settings(self._settings)
        self._show_toast("Settings saved", color=GREEN)
        self._write_log("Settings saved")
    
    def _add_custom_cmd(self, *_):
        phrase = self._cc_phrase.text.strip().lower()
        pkg = self._cc_pkg.text.strip()
        if not phrase or not pkg:
            self._show_toast("Fill both fields", color=AMBER)
            return
        self._settings["custom_cmds"][phrase] = pkg
        save_settings(self._settings)
        self._cc_phrase.text = ""
        self._cc_pkg.text = ""
        self._show_toast(f"Added: {phrase}", color=GREEN)
        self._write_log(f"Custom cmd: '{phrase}' → {pkg}")
    
    # ── Toggle callbacks ──────────────────────────────────────────────────
    def _on_active_tap(self, state):
        if state:
            self._tog_inactive.set_state(False, silent=True)
            self._activate()
        else:
            self._tog_inactive.set_state(True, silent=True)
            self._deactivate()
    
    def _on_inactive_tap(self, state):
        if state:
            self._tog_active.set_state(False, silent=True)
            self._deactivate()
        else:
            self._tog_active.set_state(True, silent=True)
            self._activate()
    
    def _activate(self):
        self._active = True
        self._waiting = False
        self._listening_for_wake = True
        self._set_status("Listening for wake word...", GREEN)
        self._hint.text = 'Say  "Hello Buddy"  to wake up'
        self._wave.start()
        
        # Start listening if Android speech is available
        if ON_ANDROID and ANDROID_SPEECH_OK:
            self._start_listening_loop()
        else:
            self._write_log("Tap the text input or use quick test buttons")
            speak_tts("Buddy is active. Type your commands or use the buttons.", 
                     self._settings["tts_enabled"])
            return
        
        self._write_log("Listener started")
        speak_tts("Buddy is active", self._settings["tts_enabled"])
    
    def _deactivate(self):
        self._active = False
        self._waiting = False
        self._listening_for_wake = True
        self._set_status("Inactive", DIM)
        self._hint.text = "Toggle Active to begin"
        self._wave.stop()
        self._write_log("Listener stopped")
        speak_tts("Buddy is sleeping", self._settings["tts_enabled"])
    
    def _set_status(self, text, color):
        self._dot.color = color
        self._stat.color = color
        self._stat.text = text
    
    # ── Voice recognition loop ────────────────────────────────────────────
    def _start_listening_loop(self):
        """Start continuous listening using Android's speech recognition"""
        def on_speech_result(text, error):
            if not self._active:
                return
            
            if error:
                # Don't log normal errors (like no speech detected)
                if error != 7:  # 7 = No match
                    self._write_log(f"Speech error: {error}")
                # Continue listening
                Clock.schedule_once(lambda dt: self._start_listening_loop(), 0.5)
                return
            
            if text:
                Clock.schedule_once(lambda dt, t=text: self._on_heard(t))
            
            # Continue listening loop
            Clock.schedule_once(lambda dt: self._start_listening_loop(), 0.5)
        
        # Start listening
        start_android_speech_listening(on_speech_result)
    
    def _on_heard(self, text):
        """Process heard text"""
        self._write_log(f'Heard: "{text}"')
        self._wave.feed(0.8)  # Visual feedback
        self._process(text)
    
    def _process(self, raw: str):
        """Process command text"""
        text = raw.lower().strip()
        now = time.time()
        
        # Check for wake word if we're in wake mode
        if self._listening_for_wake:
            if WAKE_WORD in text:
                self._waiting = True
                self._listening_for_wake = False
                self._conv_deadline = now + CONV_TIMEOUT
                self._set_status("Awake! Listening for command...", AMBER)
                self._hint.text = "Say your command..."
                self._show_toast("Yes Buddy! Listening", color=AMBER)
                self._write_log("Wake word detected")
                speak_tts("Yes, I'm listening", self._settings["tts_enabled"])
                return
            else:
                # Ignore other words when not woken up
                return
        
        # Check conversation timeout
        if self._settings["conv_mode"] and self._waiting and now < self._conv_deadline:
            self._conv_deadline = now + CONV_TIMEOUT
        elif self._waiting and now > self._conv_deadline:
            self._waiting = False
            self._listening_for_wake = True
            self._set_status("Listening for wake word...", GREEN)
            self._hint.text = 'Say  "Hello Buddy"  to wake up'
            self._write_log("Conversation timed out")
            speak_tts("Conversation timeout. Say Hello Buddy to wake me again.", 
                     self._settings["tts_enabled"])
            return
        
        if not self._waiting:
            return
        
        # Process command
        action, detail = parse_intent(text)
        
        # Check custom commands
        for phrase, pkg in self._settings.get("custom_cmds", {}).items():
            if phrase in text:
                action, detail = "custom", pkg
                break
        
        self._dispatch(action, detail, text)
    
    def _dispatch(self, action: str, detail: str, raw: str):
        def _done(ok: bool, msg: str, tts_msg: str = ""):
            col = GREEN if ok else AMBER
            self._show_toast(msg, color=col)
            self._write_log(msg)
            speak_tts(tts_msg or msg, self._settings["tts_enabled"])
            
            if not self._settings["conv_mode"]:
                # Go back to wake word listening
                self._waiting = False
                self._listening_for_wake = True
                self._set_status("Listening for wake word...", GREEN)
                self._hint.text = 'Say  "Hello Buddy"  to wake up'
            else:
                self._set_status("Conversation mode...", AMBER)
                # Reset timeout
                self._conv_deadline = time.time() + CONV_TIMEOUT
        
        if action == "stop":
            self._waiting = False
            self._listening_for_wake = True
            self._deactivate()
            self._tog_active.set_state(False, silent=True)
            self._tog_inactive.set_state(True, silent=True)
            _done(True, "Goodbye! Buddy sleeping", "Goodbye")
            return
        
        if action == "help":
            msg = "Commands: open app, search, alarm, timer, volume, torch, time, date, battery, stop"
            _done(True, "Commands in log", msg)
            self._write_log(msg)
            return
        
        if action == "time":
            s = datetime.now().strftime("%I:%M %p")
            _done(True, f"Time: {s}", f"The time is {s}")
            return
        
        if action == "date":
            s = datetime.now().strftime("%A, %B %d, %Y")
            _done(True, f"Date: {s}", s)
            return
        
        if action == "battery":
            msg = get_battery()
            _done(True, msg, msg)
            return
        
        if action in ("vol_up", "vol_down", "mute"):
            _done(True, action.replace("_", " ").capitalize())
            return
        
        if action == "torch":
            threading.Thread(target=toggle_torch, daemon=True).start()
            _done(True, "Toggling flashlight")
            return
        
        if action == "alarm":
            def _a():
                ok, msg = set_alarm(detail)
                Clock.schedule_once(lambda dt: _done(ok, msg))
            threading.Thread(target=_a, daemon=True).start()
            return
        
        if action == "timer":
            secs = int(detail) if detail.isdigit() else 60
            def _t():
                ok, msg = set_timer(secs)
                Clock.schedule_once(lambda dt: _done(ok, msg))
            threading.Thread(target=_t, daemon=True).start()
            return
        
        if action == "search":
            def _s():
                ok, msg = web_search(detail)
                Clock.schedule_once(lambda dt: _done(ok, msg))
            threading.Thread(target=_s, daemon=True).start()
            return
        
        if action == "open_app":
            def _o():
                ok, msg = launch_app(detail)
                Clock.schedule_once(lambda dt: _done(ok, msg))
            threading.Thread(target=_o, daemon=True).start()
            return
        
        if action == "custom":
            def _c():
                ok = _am("start", "-n", f"{detail}/.MainActivity")
                msg = f"Opened {detail}" if ok else f"Could not open {detail}"
                Clock.schedule_once(lambda dt: _done(ok, msg))
            threading.Thread(target=_c, daemon=True).start()
            return
        
        _done(False, f'Unknown: "{raw}"', "Sorry, I didn't understand")
    
    # ── UI utilities ──────────────────────────────────────────────────────
    def _show_toast(self, msg, color=ACCENT):
        try:
            Toast(msg, color=color).open()
        except Exception as e:
            self._write_log(f"Toast error: {e}")
    
    def _write_log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}]  {msg}"
        self._log_lines.appendleft(line)
        display = "\n".join(list(self._log_lines)[:10])
        Clock.schedule_once(
            lambda dt, d=display: setattr(self._log_lbl, "text", d)
        )
        if self._settings.get("log_to_file") and LOG_FILE:
            try:
                with open(LOG_FILE, "a") as f:
                    f.write(line + "\n")
            except Exception:
                pass
    
    def _clear_log(self, *_):
        self._log_lines.clear()
        self._log_lbl.text = "Log cleared."
        try:
            if LOG_FILE:
                open(LOG_FILE, "w").close()
        except Exception:
            pass

# ════════════════════════════════════════════════════════════════
#  APP ENTRY POINT
# ════════════════════════════════════════════════════════════════
class BuddyAssistantApp(App):
    
    def build(self):
        self.title = "Buddy Assistant"
        
        # Set window colour
        Window.clearcolor = (0.04, 0.04, 0.06, 1)
        
        # Initialise paths after Android storage is mounted
        _init_paths()
        
        # Initialize TTS on the main thread
        if ON_ANDROID:
            Clock.schedule_once(lambda dt: _init_android_tts(), 0)
        else:
            _init_desktop_tts()
        
        try:
            return BuddyUI()
        except Exception as e:
            # Show error on screen
            return Label(
                text=f"Startup error:\n{e}",
                color=(1, 0.3, 0.3, 1),
                font_size=dp(13),
                halign="center",
                valign="middle"
            )
    
    def on_stop(self):
        if ON_ANDROID and _android_tts is not None:
            try:
                _android_tts.shutdown()
            except Exception:
                pass
        if not ON_ANDROID and _desktop_tts is not None:
            try:
                _desktop_tts.stop()
            except Exception:
                pass

if __name__ == "__main__":
    BuddyAssistantApp().run()
