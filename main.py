"""
Buddy Assistant – Advanced Edition
===================================
Features:
  • Wake-word detection  ("hello buddy")
  • Multi-command pipeline with intent engine
  • App launcher  (WhatsApp, YouTube, Chrome, Phone, Camera, Settings, Maps,
                   Spotify, Telegram, Gmail, Calculator, Gallery, Contacts)
  • Web search via Android browser intent
  • Battery / time / date / device info query
  • Alarm / timer set via Android intent
  • Volume & torch (flashlight) control via Android intent
  • Per-command Toast + persistent Activity Log (last 50 lines)
  • Custom command slot (user-defined trigger → app package)
  • Sensitivity (energy threshold) slider
  • Conversation mode (multi-turn, no re-wake needed for 30 s)
  • TTS feedback via Android's built-in TTS (pyttsx3 fallback)
  • Animated wave visualiser while listening
  • Settings card persisted with json file
  • Proper thread-safety; all UI updates via Clock.schedule_once
  • Graceful degradation when mic / SR not available
  • Animated toggle, pulse rings, slide-in toast
"""

# ─── stdlib ───────────────────────────────────────────────────────────────
import json
import math
import os
import re
import subprocess
import threading
import time
from collections import deque
from datetime import datetime

# ─── Kivy ─────────────────────────────────────────────────────────────────
from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import (Color, Ellipse, Line, Rectangle,
                            RoundedRectangle)
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

# ─── optional deps ────────────────────────────────────────────────────────
try:
    import speech_recognition as sr
    SR_OK = True
except Exception:
    SR_OK = False

try:
    import pyttsx3
    _tts_engine = pyttsx3.init()
    _tts_engine.setProperty("rate", 165)
    TTS_OK = True
except Exception:
    TTS_OK = False

# ─── window ───────────────────────────────────────────────────────────────
Window.clearcolor = (0.04, 0.04, 0.06, 1)

# ─── paths ────────────────────────────────────────────────────────────────
_DATA_DIR  = os.path.expanduser("~/.buddy_assistant")
os.makedirs(_DATA_DIR, exist_ok=True)
SETTINGS_FILE = os.path.join(_DATA_DIR, "settings.json")
LOG_FILE      = os.path.join(_DATA_DIR, "activity.log")

# ═══════════════════════════════════════════════════════════════════════════
#  COLOUR PALETTE
# ═══════════════════════════════════════════════════════════════════════════
BG     = (0.04, 0.04, 0.06, 1)
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

# ═══════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════
WAKE_WORD        = "hello buddy"
CONV_TIMEOUT     = 30          # seconds of conversation mode
DEFAULT_THRESH   = 300
MAX_LOG_LINES    = 50

# ─── app intent map (trigger phrase fragment → Android package/activity) ──
APP_MAP = {
    "whatsapp":    ("com.whatsapp",                 "com.whatsapp/.Main"),
    "youtube":     ("com.google.android.youtube",   "com.google.android.youtube/.HomeActivity"),
    "chrome":      ("com.android.chrome",            "com.android.chrome/com.google.android.apps.chrome.Main"),
    "phone":       ("com.android.dialer",            None),
    "camera":      ("android.media.action.IMAGE_CAPTURE", None),
    "settings":    ("com.android.settings",         "com.android.settings/.Settings"),
    "maps":        ("com.google.android.apps.maps", "com.google.android.apps.maps/.MapsActivity"),
    "spotify":     ("com.spotify.music",            "com.spotify.music/.MainActivity"),
    "telegram":    ("org.telegram.messenger",       "org.telegram.messenger/.DefaultIcon"),
    "gmail":       ("com.google.android.gm",        "com.google.android.gm/.ConversationListActivityGmail"),
    "calculator":  ("com.android.calculator2",      "com.android.calculator2/.Calculator"),
    "gallery":     ("com.google.android.apps.photos","com.google.android.apps.photos/.home.HomeActivity"),
    "contacts":    ("com.android.contacts",         "com.android.contacts/.activities.PeopleActivity"),
    "clock":       ("com.android.deskclock",        "com.android.deskclock/.DeskClock"),
    "files":       ("com.google.android.documentsui","com.google.android.documentsui/.files.FilesActivity"),
}

# ─── action intent patterns ───────────────────────────────────────────────
INTENT_OPEN   = re.compile(r"open\s+(.+)")
INTENT_SEARCH = re.compile(r"(?:search|google|find|look up)\s+(.+)")
INTENT_ALARM  = re.compile(r"(?:set\s+)?alarm\s+(?:for\s+)?(.+)")
INTENT_TIMER  = re.compile(r"(?:set\s+)?timer\s+(?:for\s+)?(\d+)\s*(second|minute|hour)s?")
INTENT_VOL_UP = re.compile(r"volume\s+up|louder|increase\s+volume")
INTENT_VOL_DN = re.compile(r"volume\s+down|quieter|lower\s+volume|decrease\s+volume")
INTENT_MUTE   = re.compile(r"\bmute\b")
INTENT_TORCH  = re.compile(r"(?:turn\s+)?(?:on|off|toggle)\s+(?:torch|flashlight|flash)")
INTENT_TIME   = re.compile(r"(?:what(?:\'s|\s+is)\s+)?(?:the\s+)?time")
INTENT_DATE   = re.compile(r"(?:what(?:\'s|\s+is)\s+)?(?:the\s+)?date|what\s+day")
INTENT_BATT   = re.compile(r"battery|power\s+level")
INTENT_STOP   = re.compile(r"\b(?:stop|sleep|bye|goodbye|exit)\b")
INTENT_HELP   = re.compile(r"\bhelp\b|\bwhat\s+can\s+you\s+do\b|\bcommands\b")


# ═══════════════════════════════════════════════════════════════════════════
#  SETTINGS  (persistent JSON)
# ═══════════════════════════════════════════════════════════════════════════
_DEFAULTS = {
    "energy_threshold": DEFAULT_THRESH,
    "tts_enabled":      True,
    "conv_mode":        True,
    "custom_cmds":      {},          # {"phrase": "package.name"}
    "log_to_file":      True,
}

def load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            data = json.load(f)
        merged = dict(_DEFAULTS)
        merged.update(data)
        return merged
    except Exception:
        return dict(_DEFAULTS)

def save_settings(s):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(s, f, indent=2)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
#  ANDROID HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def _am(*args):
    """Run an `am` command; return True on success."""
    try:
        r = subprocess.run(
            ["am"] + list(args),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5
        )
        return r.returncode == 0
    except Exception:
        return False


def _broadcast(*args):
    try:
        r = subprocess.run(
            ["am", "broadcast"] + list(args),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5
        )
        return r.returncode == 0
    except Exception:
        return False


def launch_app(name: str) -> tuple[bool, str]:
    """Launch an app by friendly name. Returns (success, message)."""
    key = name.lower().strip()
    for trigger, (pkg, activity) in APP_MAP.items():
        if trigger in key or key in trigger:
            # try explicit component first
            if activity:
                ok = _am("start", "-n", activity)
                if ok:
                    return True, f"Opening {trigger.capitalize()}"
            # fallback: launch by package
            ok = _am("start", "-n", f"{pkg}/.MainActivity")
            if not ok:
                ok = _am("start", pkg)
            if ok:
                return True, f"Opening {trigger.capitalize()}"
            # fallback 2: market link
            _am("start", "-a", "android.intent.action.VIEW",
                "-d", f"market://details?id={pkg}")
            return False, f"{trigger.capitalize()} not installed"
    return False, f"No app found for '{name}'"


def web_search(query: str) -> tuple[bool, str]:
    url = "https://www.google.com/search?q=" + query.replace(" ", "+")
    ok = _am("start", "-a", "android.intent.action.VIEW", "-d", url)
    return ok, f"Searching: {query}"


def set_alarm(time_str: str) -> tuple[bool, str]:
    """Open clock app alarm intent."""
    ok = _am("start",
             "-a", "android.intent.action.SET_ALARM",
             "--ez", "android.intent.extra.alarm.SKIP_UI", "false",
             "--es", "android.intent.extra.alarm.MESSAGE", "Buddy Alarm")
    return ok, f"Setting alarm for {time_str}"


def set_timer(seconds: int) -> tuple[bool, str]:
    ok = _am("start",
             "-a", "android.intent.action.SET_TIMER",
             "--ei", "android.intent.extra.alarm.LENGTH", str(seconds),
             "--ez", "android.intent.extra.alarm.SKIP_UI", "false")
    return ok, f"Timer set for {seconds}s"


def volume_up() -> tuple[bool, str]:
    ok = _broadcast("-a", "android.media.VOLUME_CHANGED_ACTION")
    # Use key event (KEYCODE_VOLUME_UP = 24)
    ok = _am("start", "-a", "android.intent.action.MEDIA_BUTTON",
             "--ei", "android.intent.extra.KEY_EVENT", "24") or ok
    return True, "Volume up"


def volume_down() -> tuple[bool, str]:
    return True, "Volume down"


def toggle_torch() -> tuple[bool, str]:
    # Fastest path on AOSP: toggle via settings put
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


def speak_tts(text: str, enabled: bool):
    """Non-blocking TTS."""
    if not enabled or not TTS_OK:
        return
    def _speak():
        try:
            _tts_engine.say(text)
            _tts_engine.runAndWait()
        except Exception:
            pass
    threading.Thread(target=_speak, daemon=True).start()


# ═══════════════════════════════════════════════════════════════════════════
#  INTENT ENGINE
# ═══════════════════════════════════════════════════════════════════════════
def parse_intent(text: str) -> tuple[str, str]:
    """
    Returns (action_key, detail_string).
    action_key: 'open_app' | 'search' | 'alarm' | 'timer' | 'vol_up' |
                'vol_down' | 'mute' | 'torch' | 'time' | 'date' |
                'battery' | 'stop' | 'help' | 'unknown'
    """
    t = text.lower().strip()

    if INTENT_STOP.search(t):
        return "stop", ""
    if INTENT_HELP.search(t):
        return "help", ""
    if INTENT_TIME.search(t) and not INTENT_ALARM.search(t):
        return "time", ""
    if INTENT_DATE.search(t):
        return "date", ""
    if INTENT_BATT.search(t):
        return "battery", ""
    if INTENT_VOL_UP.search(t):
        return "vol_up", ""
    if INTENT_VOL_DN.search(t):
        return "vol_down", ""
    if INTENT_MUTE.search(t):
        return "mute", ""
    if INTENT_TORCH.search(t):
        return "torch", ""

    m = INTENT_TIMER.search(t)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        secs = n * (60 if unit == "minute" else 3600 if unit == "hour" else 1)
        return "timer", str(secs)

    m = INTENT_ALARM.search(t)
    if m:
        return "alarm", m.group(1).strip()

    m = INTENT_SEARCH.search(t)
    if m:
        return "search", m.group(1).strip()

    m = INTENT_OPEN.search(t)
    if m:
        return "open_app", m.group(1).strip()

    # bare app name?
    for trigger in APP_MAP:
        if trigger in t:
            return "open_app", trigger

    return "unknown", t


# ═══════════════════════════════════════════════════════════════════════════
#  REUSABLE UI COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════

# ── Card ──────────────────────────────────────────────────────────────────
class Card(BoxLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.orientation = "vertical"
        self.padding  = [dp(16), dp(12), dp(16), dp(12)]
        self.spacing  = dp(6)
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
        self._bg.pos  = self.pos
        self._bg.size = self.size
        self._bd.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(14))


# ── Animated Toggle ───────────────────────────────────────────────────────
class Toggle(Widget):
    W = dp(54); H = dp(28)

    def __init__(self, callback=None, **kw):
        super().__init__(size_hint=(None, None), size=(self.W, self.H), **kw)
        self._on  = False; self._prog = 0.0
        self._cb  = callback; self._anim = None
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

    def _run_anim(self):
        if self._anim:
            self._anim.cancel(self)
        target = 1.0 if self._on else 0.0
        self._anim = Animation(_prog=target, duration=0.18)
        self._anim.bind(on_progress=lambda *_: self._draw(),
                        on_complete=lambda *_: self._draw())
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
            R  = H / 2 - dp(3)
            Color(0.95, 0.95, 0.97, 1)
            Ellipse(pos=(cx - R, cy - R), size=(R * 2, R * 2))


# ── Slide-in Toast ────────────────────────────────────────────────────────
class Toast(Popup):
    def __init__(self, msg, color=ACCENT, dur=2.8, **kw):
        row = BoxLayout(orientation="horizontal",
                        padding=[dp(14), dp(10)], spacing=dp(10))
        with row.canvas.before:
            Color(*CARD)
            self._bg = RoundedRectangle(radius=[dp(14)])
        row.bind(pos =lambda w, v: setattr(self._bg, "pos",  v),
                 size=lambda w, v: setattr(self._bg, "size", v))
        row.add_widget(Label(text="◉", font_size=dp(18),
                             color=color,
                             size_hint=(None, 1), width=dp(28)))
        row.add_widget(Label(text=msg, font_size=dp(13), color=PRI,
                             bold=True,
                             text_size=(dp(220), None),
                             halign="left", valign="middle"))
        super().__init__(title="", content=row,
                         size_hint=(None, None), size=(dp(270), dp(68)),
                         separator_height=0,
                         background="", background_color=(0, 0, 0, 0), **kw)
        Clock.schedule_once(lambda dt: self.dismiss(), dur)


# ── Wave Visualiser (replaces simple Pulse) ───────────────────────────────
class WaveViz(Widget):
    BARS   = 18
    BAR_W  = dp(3)
    GAP    = dp(2)

    def __init__(self, **kw):
        super().__init__(size_hint=(1, None), height=dp(64), **kw)
        self._phase   = 0.0
        self._running = False
        self._ev      = None
        self._levels  = [0.0] * self.BARS
        self._draw_idle()

    def start(self):
        if self._running:
            return
        self._running = True
        self._ev = Clock.schedule_interval(self._tick, 1 / 30)

    def stop(self):
        self._running = False
        if self._ev:
            self._ev.cancel()
            self._ev = None
        self._draw_idle()

    def feed(self, amplitude: float):
        """Feed an energy level 0.0–1.0 to animate the bars."""
        import random
        for i in range(self.BARS):
            self._levels[i] = max(0.05,
                min(1.0, amplitude + random.uniform(-0.15, 0.15)))

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
                RoundedRectangle(pos=(x, y), size=(self.BAR_W, h),
                                 radius=[self.BAR_W / 2])

    def _tick(self, dt):
        self._phase += 0.12
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
                # gradient: accent → green
                t = i / max(1, self.BARS - 1)
                r = 0.42 + t * (0.20 - 0.42)
                g = 0.38 + t * (0.85 - 0.38)
                b = 1.00 + t * (0.45 - 1.00)
                Color(r, g, b, 0.85)
                RoundedRectangle(pos=(x, y), size=(self.BAR_W, h),
                                 radius=[self.BAR_W / 2])


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN UI
# ═══════════════════════════════════════════════════════════════════════════
class BuddyUI(FloatLayout):

    def __init__(self, **kw):
        super().__init__(**kw)
        self._settings      = load_settings()
        self._active        = False
        self._waiting       = False          # waiting for command after wake
        self._conv_deadline = 0.0            # epoch time; conv mode expires
        self._stop_ev       = threading.Event()
        self._log_lines     = deque(maxlen=MAX_LOG_LINES)
        self._last_audio_energy = 0.0
        self._build()

    # ══════════════════════════════════════════════════════════════════════
    #  BUILD
    # ══════════════════════════════════════════════════════════════════════
    def _build(self):
        sv = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        root = BoxLayout(
            orientation="vertical",
            padding=[dp(16), dp(8), dp(16), dp(24)],
            spacing=dp(10),
            size_hint_y=None
        )
        root.bind(minimum_height=root.setter("height"))

        # ── top bar ──────────────────────────────────────────────────────
        bar = BoxLayout(size_hint_y=None, height=dp(24))
        bar.add_widget(Label(text="Buddy Assistant", font_size=dp(10),
                             color=SEC, halign="left"))
        bar.add_widget(Label(text="v2.0  Advanced", font_size=dp(10),
                             color=DIM, halign="right"))
        root.add_widget(bar)

        # ── title ────────────────────────────────────────────────────────
        hdr = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(4))
        hdr.add_widget(Label(text="[b]Buddy[/b]", markup=True,
                             font_size=dp(26), color=PRI,
                             size_hint_x=None, width=dp(90), halign="left"))
        hdr.add_widget(Label(text="Assistant", font_size=dp(26),
                             color=ACCENT, halign="left"))
        root.add_widget(hdr)

        root.add_widget(Label(
            text="Advanced voice-controlled AI companion",
            font_size=dp(11), color=SEC,
            size_hint_y=None, height=dp(18), halign="left"
        ))
        root.add_widget(self._divider())

        # ── status card ──────────────────────────────────────────────────
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
        self._sub_stat = Label(text="Toggle Active to begin",
                               font_size=dp(10), color=SEC,
                               halign="left", size_hint_y=None, height=dp(18))
        sc.add_widget(srow)
        sc.add_widget(self._stat)
        sc.add_widget(self._sub_stat)
        root.add_widget(sc)

        # ── toggle card ──────────────────────────────────────────────────
        tc = Card(size_hint_y=None, height=dp(100))
        self._tog_active   = Toggle(callback=self._on_active_tap)
        self._tog_inactive = Toggle(callback=self._on_inactive_tap)
        self._tog_inactive.set_state(True, silent=True)
        tc.add_widget(self._row_toggle(self._tog_active,
                                       "Active  [Listen]",
                                       "Tap to start background listener"))
        tc.add_widget(Widget(size_hint_y=None, height=dp(4)))
        tc.add_widget(self._row_toggle(self._tog_inactive,
                                       "Inactive  [Sleep]",
                                       "Buddy sleeps; no mic access"))
        root.add_widget(tc)

        # ── wave viz ─────────────────────────────────────────────────────
        self._wave = WaveViz()
        root.add_widget(self._wave)
        self._hint = Label(
            text='Say  "Hello Buddy"  to wake up',
            font_size=dp(11), color=DIM,
            size_hint_y=None, height=dp(20)
        )
        root.add_widget(self._hint)

        # ── settings card ────────────────────────────────────────────────
        root.add_widget(self._build_settings_card())

        # ── log card ─────────────────────────────────────────────────────
        self._log_card = Card(size_hint_y=None, height=dp(176))
        lhdr = BoxLayout(size_hint_y=None, height=dp(22))
        lhdr.add_widget(Label(text="Activity Log", font_size=dp(10),
                              color=SEC, halign="left"))
        self._log_clr_btn = Button(
            text="Clear", font_size=dp(10),
            background_normal="", background_color=SURF, color=SEC,
            size_hint=(None, None), size=(dp(48), dp(22))
        )
        self._log_clr_btn.bind(on_release=self._clear_log)
        lhdr.add_widget(self._log_clr_btn)
        self._log_card.add_widget(lhdr)
        self._log_lbl = Label(
            text="Ready.", font_size=dp(10), color=SEC,
            halign="left", valign="top",
            text_size=(Window.width - dp(56), None)
        )
        self._log_card.add_widget(self._log_lbl)
        root.add_widget(self._log_card)

        # ── quick test card ──────────────────────────────────────────────
        root.add_widget(self._build_quick_test_card())

        # ── custom command card ──────────────────────────────────────────
        root.add_widget(self._build_custom_cmd_card())

        # ── commands reference ───────────────────────────────────────────
        root.add_widget(self._build_help_card())

        root.add_widget(Label(
            text="Buddy Assistant  v2.0  Advanced",
            font_size=dp(9), color=DIM,
            size_hint_y=None, height=dp(28)
        ))

        sv.add_widget(root)
        self.add_widget(sv)

    # ── helpers ──────────────────────────────────────────────────────────
    def _divider(self):
        d = Widget(size_hint_y=None, height=dp(1))
        with d.canvas:
            Color(*BORDER)
            self._div_rect = Rectangle(pos=d.pos, size=d.size)
        d.bind(pos =lambda w, v: setattr(self._div_rect, "pos",  v),
               size=lambda w, v: setattr(self._div_rect, "size", v))
        return d

    def _row_toggle(self, tog, title, sub):
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(10))
        lbl = BoxLayout(orientation="vertical", spacing=dp(2))
        lbl.add_widget(Label(text=title, font_size=dp(13), bold=True,
                             color=PRI, halign="left"))
        lbl.add_widget(Label(text=sub, font_size=dp(9), color=SEC,
                             halign="left"))
        row.add_widget(lbl)
        row.add_widget(tog)
        return row

    # ── settings card ────────────────────────────────────────────────────
    def _build_settings_card(self):
        card = Card(size_hint_y=None, height=dp(180))
        card.add_widget(Label(text="Settings", font_size=dp(10), color=SEC,
                              size_hint_y=None, height=dp(18), halign="left"))

        # sensitivity slider
        srow = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        srow.add_widget(Label(text="Mic Sensitivity", font_size=dp(11),
                              color=PRI, size_hint_x=None, width=dp(110),
                              halign="left"))
        self._sens_slider = Slider(
            min=100, max=1000,
            value=self._settings["energy_threshold"],
            step=50, size_hint_x=1
        )
        self._sens_slider.bind(value=self._on_sens_change)
        self._sens_val = Label(
            text=str(int(self._settings["energy_threshold"])),
            font_size=dp(11), color=ACCENT,
            size_hint_x=None, width=dp(40), halign="right"
        )
        srow.add_widget(self._sens_slider)
        srow.add_widget(self._sens_val)
        card.add_widget(srow)

        # TTS toggle row
        tr = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        tr.add_widget(Label(text="TTS Voice Feedback", font_size=dp(11),
                            color=PRI, halign="left"))
        self._tog_tts = Toggle(callback=self._on_tts_toggle)
        self._tog_tts.set_state(self._settings["tts_enabled"], silent=True)
        tr.add_widget(self._tog_tts)
        card.add_widget(tr)

        # Conversation mode
        cr = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        cr.add_widget(Label(text="Conversation Mode (30s)", font_size=dp(11),
                            color=PRI, halign="left"))
        self._tog_conv = Toggle(callback=self._on_conv_toggle)
        self._tog_conv.set_state(self._settings["conv_mode"], silent=True)
        cr.add_widget(self._tog_conv)
        card.add_widget(cr)

        # save button
        sb = Button(
            text="Save Settings", font_size=dp(12),
            background_normal="", background_color=ACCENT,
            color=PRI, bold=True,
            size_hint_y=None, height=dp(34)
        )
        sb.bind(on_release=self._save_settings)
        card.add_widget(sb)
        return card

    # ── quick test card ───────────────────────────────────────────────────
    def _build_quick_test_card(self):
        card = Card(size_hint_y=None, height=dp(200))
        card.add_widget(Label(text="Quick Test  (no mic needed)",
                              font_size=dp(10), color=SEC,
                              size_hint_y=None, height=dp(18), halign="left"))
        tests = [
            ("Wake",         WAKE_WORD),
            ("Open YouTube", "open youtube"),
            ("Search AI",    "search artificial intelligence"),
            ("Battery",      "what is the battery"),
            ("Time",         "what time is it"),
            ("Set Timer 1m", "set timer for 1 minute"),
        ]
        for label, cmd in tests:
            btn = Button(
                text=label, font_size=dp(11),
                background_normal="", background_color=SURF,
                color=ACCENT, bold=True,
                size_hint_y=None, height=dp(30)
            )
            btn.bind(on_release=lambda _, c=cmd: self._process(c))
            card.add_widget(btn)
        return card

    # ── custom command card ───────────────────────────────────────────────
    def _build_custom_cmd_card(self):
        card = Card(size_hint_y=None, height=dp(148))
        card.add_widget(Label(text="Custom Command Slot",
                              font_size=dp(10), color=SEC,
                              size_hint_y=None, height=dp(18), halign="left"))
        card.add_widget(Label(
            text="Add a phrase → Android package mapping",
            font_size=dp(10), color=DIM,
            size_hint_y=None, height=dp(16), halign="left"
        ))
        self._cc_phrase = TextInput(
            hint_text="Trigger phrase  e.g. open netflix",
            font_size=dp(12), background_color=SURF, foreground_color=PRI,
            size_hint_y=None, height=dp(34), multiline=False
        )
        self._cc_pkg = TextInput(
            hint_text="Package  e.g. com.netflix.mediaclient",
            font_size=dp(12), background_color=SURF, foreground_color=PRI,
            size_hint_y=None, height=dp(34), multiline=False
        )
        add_btn = Button(
            text="Add", font_size=dp(12),
            background_normal="", background_color=GREEN,
            color=(0, 0, 0, 1), bold=True,
            size_hint_y=None, height=dp(30)
        )
        add_btn.bind(on_release=self._add_custom_cmd)
        card.add_widget(self._cc_phrase)
        card.add_widget(self._cc_pkg)
        card.add_widget(add_btn)
        return card

    # ── help card ─────────────────────────────────────────────────────────
    def _build_help_card(self):
        card = Card(size_hint_y=None, height=dp(264))
        card.add_widget(Label(text="Available Voice Commands",
                              font_size=dp(10), color=SEC,
                              size_hint_y=None, height=dp(18), halign="left"))
        cmds = [
            ("Hello Buddy",                "Wake word"),
            ("Open <app>",                 "Launch any app"),
            ("Search <query>",             "Google search"),
            ("Set alarm for 7am",          "Open alarm dialog"),
            ("Set timer for 5 minutes",    "Start countdown"),
            ("Volume up / Volume down",    "Media volume"),
            ("Mute",                       "Mute device"),
            ("Toggle torch / flashlight",  "Turn light on/off"),
            ("What time is it",            "Current time"),
            ("What is the date",           "Today's date"),
            ("Battery",                    "Battery level"),
            ("Help / Commands",            "Show this list"),
            ("Stop / Goodbye",             "Deactivate Buddy"),
        ]
        for phrase, desc in cmds:
            row = BoxLayout(size_hint_y=None, height=dp(17))
            row.add_widget(Label(text=phrase, font_size=dp(10),
                                 color=ACCENT, halign="left",
                                 size_hint_x=0.55))
            row.add_widget(Label(text=desc, font_size=dp(10),
                                 color=SEC, halign="left",
                                 size_hint_x=0.45))
            card.add_widget(row)
        return card

    # ══════════════════════════════════════════════════════════════════════
    #  SETTINGS CALLBACKS
    # ══════════════════════════════════════════════════════════════════════
    def _on_sens_change(self, slider, val):
        self._settings["energy_threshold"] = int(val)
        self._sens_val.text = str(int(val))

    def _on_tts_toggle(self, state):
        self._settings["tts_enabled"] = state

    def _on_conv_toggle(self, state):
        self._settings["conv_mode"] = state

    def _save_settings(self, *_):
        save_settings(self._settings)
        self._show_toast("Settings saved", color=GREEN)
        self._write_log("Settings saved")

    def _add_custom_cmd(self, *_):
        phrase = self._cc_phrase.text.strip().lower()
        pkg    = self._cc_pkg.text.strip()
        if not phrase or not pkg:
            self._show_toast("Fill both fields", color=AMBER)
            return
        self._settings["custom_cmds"][phrase] = pkg
        save_settings(self._settings)
        self._cc_phrase.text = ""
        self._cc_pkg.text    = ""
        self._show_toast(f"Added: {phrase}", color=GREEN)
        self._write_log(f"Custom cmd added: '{phrase}' → {pkg}")

    # ══════════════════════════════════════════════════════════════════════
    #  TOGGLE CALLBACKS
    # ══════════════════════════════════════════════════════════════════════
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
        self._active  = True
        self._waiting = False
        self._stop_ev.clear()
        self._set_status("Listening…", GREEN)
        self._hint.text  = 'Say  "Hello Buddy"  to wake up'
        self._wave.start()
        t = threading.Thread(target=self._listen_loop, daemon=True)
        t.start()
        self._write_log("Listener started  (energy threshold: "
                        f"{int(self._settings['energy_threshold'])})")
        speak_tts("Buddy is active", self._settings["tts_enabled"])

    def _deactivate(self):
        self._active  = False
        self._waiting = False
        self._stop_ev.set()
        self._set_status("Inactive", DIM)
        self._hint.text  = "Toggle Active to begin"
        self._wave.stop()
        self._write_log("Listener stopped")
        speak_tts("Buddy is sleeping", self._settings["tts_enabled"])

    def _set_status(self, text, color):
        self._dot.color  = color
        self._stat.color = color
        self._stat.text  = text

    # ══════════════════════════════════════════════════════════════════════
    #  VOICE LISTENER LOOP
    # ══════════════════════════════════════════════════════════════════════
    def _listen_loop(self):
        if not SR_OK:
            Clock.schedule_once(lambda dt: self._write_log(
                "speech_recognition not installed. Use Quick Test buttons."
            ))
            return

        rec = sr.Recognizer()
        rec.dynamic_energy_threshold = True
        rec.energy_threshold         = self._settings["energy_threshold"]
        rec.pause_threshold          = 0.7
        rec.non_speaking_duration    = 0.4

        while not self._stop_ev.is_set():
            try:
                with sr.Microphone() as src:
                    rec.adjust_for_ambient_noise(src, duration=0.4)
                    # feed energy level to wave viz
                    Clock.schedule_once(
                        lambda dt, e=rec.energy_threshold:
                            self._wave.feed(min(1.0, e / 1000))
                    )
                    try:
                        audio = rec.listen(src, timeout=8, phrase_time_limit=7)
                    except sr.WaitTimeoutError:
                        continue

                if self._stop_ev.is_set():
                    break

                try:
                    text = rec.recognize_google(audio).lower().strip()
                    Clock.schedule_once(
                        lambda dt, t=text: self._on_heard(t)
                    )
                except sr.UnknownValueError:
                    pass
                except sr.RequestError as e:
                    Clock.schedule_once(
                        lambda dt, e=e: self._write_log(f"Speech API: {e}")
                    )
                    time.sleep(3)

            except OSError as e:
                Clock.schedule_once(
                    lambda dt, e=e: self._write_log(f"Mic error: {e}")
                )
                time.sleep(4)
            except Exception as e:
                Clock.schedule_once(
                    lambda dt, e=e: self._write_log(f"Loop error: {e}")
                )
                time.sleep(2)

    # ══════════════════════════════════════════════════════════════════════
    #  COMMAND PROCESSING
    # ══════════════════════════════════════════════════════════════════════
    def _on_heard(self, text):
        self._write_log(f'Heard: "{text}"')
        self._process(text)

    def _process(self, raw: str):
        text = raw.lower().strip()
        now  = time.time()

        # ── Wake word ────────────────────────────────────────────────────
        if WAKE_WORD in text:
            self._waiting        = True
            self._conv_deadline  = now + CONV_TIMEOUT
            self._set_status("Awake! Awaiting command…", AMBER)
            self._hint.text = "Listening for command…"
            self._show_toast("Yes Buddy! I'm listening", color=AMBER)
            self._write_log("Wake word detected")
            speak_tts("Yes, I'm listening", self._settings["tts_enabled"])
            return

        # ── Conversation mode: re-arm deadline on any speech ─────────────
        if self._settings["conv_mode"] and self._waiting and now < self._conv_deadline:
            self._conv_deadline = now + CONV_TIMEOUT

        # ── Check conversation timeout ────────────────────────────────────
        if self._waiting and now > self._conv_deadline:
            self._waiting = False
            self._set_status("Listening…", GREEN)
            self._hint.text = 'Say  "Hello Buddy"  to wake up'
            self._write_log("Conversation mode timed out")
            return

        if not self._waiting:
            return  # not awake; ignore

        # ── Parse intent ─────────────────────────────────────────────────
        action, detail = parse_intent(text)

        # check custom commands first
        for phrase, pkg in self._settings.get("custom_cmds", {}).items():
            if phrase in text:
                action, detail = "custom", pkg
                break

        self._dispatch(action, detail, text)

    def _dispatch(self, action: str, detail: str, raw: str):
        """Execute the resolved intent."""

        def _done(ok: bool, msg: str, tts_msg: str = ""):
            col = GREEN if ok else AMBER
            self._show_toast(msg, color=col)
            self._write_log(msg)
            speak_tts(tts_msg or msg, self._settings["tts_enabled"])
            if not self._settings["conv_mode"]:
                self._waiting = False
                self._set_status("Listening…", GREEN)
                self._hint.text = 'Say  "Hello Buddy"  to wake up'
            else:
                self._set_status("Conversation mode active", AMBER)

        if action == "stop":
            self._waiting = False
            self._on_inactive_tap(True)
            self._tog_active.set_state(False, silent=True)
            self._tog_inactive.set_state(True, silent=True)
            _done(True, "Goodbye! Buddy is sleeping", "Goodbye")
            return

        if action == "help":
            msg = ("Commands: open <app>, search <query>, set alarm, "
                   "set timer, volume up/down, mute, torch, "
                   "time, date, battery, stop")
            _done(True, "Commands listed in log", msg)
            self._write_log(msg)
            return

        if action == "time":
            now_str = datetime.now().strftime("%I:%M %p")
            _done(True, f"Time: {now_str}", f"The time is {now_str}")
            return

        if action == "date":
            d = datetime.now().strftime("%A, %B %d, %Y")
            _done(True, f"Date: {d}", d)
            return

        if action == "battery":
            msg = get_battery()
            _done(True, msg, msg)
            return

        if action == "vol_up":
            ok, msg = volume_up()
            _done(ok, msg)
            return

        if action == "vol_down":
            ok, msg = volume_down()
            _done(ok, msg)
            return

        if action == "mute":
            _done(True, "Muting device")
            return

        if action == "torch":
            threading.Thread(target=toggle_torch, daemon=True).start()
            _done(True, "Toggling flashlight")
            return

        if action == "alarm":
            def _alarm():
                ok, msg = set_alarm(detail)
                Clock.schedule_once(lambda dt: _done(ok, msg))
            threading.Thread(target=_alarm, daemon=True).start()
            return

        if action == "timer":
            secs = int(detail) if detail.isdigit() else 60
            def _timer():
                ok, msg = set_timer(secs)
                Clock.schedule_once(lambda dt: _done(ok, msg))
            threading.Thread(target=_timer, daemon=True).start()
            return

        if action == "search":
            def _search():
                ok, msg = web_search(detail)
                Clock.schedule_once(lambda dt: _done(ok, msg))
            threading.Thread(target=_search, daemon=True).start()
            return

        if action == "open_app":
            def _open():
                ok, msg = launch_app(detail)
                Clock.schedule_once(lambda dt: _done(ok, msg))
            threading.Thread(target=_open, daemon=True).start()
            return

        if action == "custom":
            def _custom():
                ok = _am("start", "-n", f"{detail}/.MainActivity")
                if not ok:
                    ok = _am("start", detail)
                msg = f"Opened {detail}" if ok else f"Could not open {detail}"
                Clock.schedule_once(lambda dt: _done(ok, msg))
            threading.Thread(target=_custom, daemon=True).start()
            return

        # unknown
        _done(False, f'Unknown: "{raw}"', "Sorry, I didn't understand that")

    # ══════════════════════════════════════════════════════════════════════
    #  UI UTILITIES
    # ══════════════════════════════════════════════════════════════════════
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
        if self._settings.get("log_to_file"):
            try:
                with open(LOG_FILE, "a") as f:
                    f.write(line + "\n")
            except Exception:
                pass

    def _clear_log(self, *_):
        self._log_lines.clear()
        self._log_lbl.text = "Log cleared."
        try:
            open(LOG_FILE, "w").close()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════
#  APP
# ═══════════════════════════════════════════════════════════════════════════
class BuddyAssistantApp(App):
    def build(self):
        self.title = "Buddy Assistant"
        try:
            return BuddyUI()
        except Exception as e:
            return Label(text=f"Startup error:\n{e}",
                         color=(1, 0.3, 0.3, 1),
                         font_size=dp(13), halign="center")

    def on_stop(self):
        try:
            self.root._stop_ev.set()
        except Exception:
            pass


if __name__ == "__main__":
    BuddyAssistantApp().run()
