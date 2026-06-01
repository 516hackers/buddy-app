from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.switch import Switch
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Rectangle, Ellipse, Line
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.animation import Animation
import threading
import subprocess
import os
import time
import platform

# ── Window setup ─────────────────────────────────────────────────────────────
Window.clearcolor = (0.04, 0.04, 0.06, 1)
Window.size = (390, 780)

# ── Optional imports ──────────────────────────────────────────────────────────
try:
    import speech_recognition as sr
    SPEECH_OK = True
except ImportError:
    SPEECH_OK = False

try:
    import pyttsx3
    TTS_OK = True
except ImportError:
    TTS_OK = False

# ── Colors ────────────────────────────────────────────────────────────────────
C_BG       = (0.04,  0.04,  0.06,  1)
C_CARD     = (0.07,  0.07,  0.10,  1)
C_SURFACE  = (0.10,  0.10,  0.15,  1)
C_ACCENT   = (0.42,  0.39,  1.00,  1)   # purple
C_GREEN    = (0.26,  0.91,  0.48,  1)
C_DIM      = (0.27,  0.27,  0.40,  1)
C_SEC      = (0.53,  0.53,  0.67,  1)
C_PRI      = (0.93,  0.93,  0.96,  1)
C_BORDER   = (0.16,  0.16,  0.24,  1)

WAKE_WORD = "hello buddy"
CMD_WA    = "open whatsapp"


# ── Helpers ───────────────────────────────────────────────────────────────────
def open_whatsapp():
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.Popen(["start", "whatsapp:"], shell=True)
        elif system == "Darwin":
            subprocess.Popen(["open", "-a", "WhatsApp"])
        else:
            # Android via am start
            subprocess.Popen(
                ["am", "start", "-n", "com.whatsapp/.Main"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        return True
    except Exception:
        return False


def speak_async(text):
    if TTS_OK:
        def _speak():
            try:
                engine = pyttsx3.init()
                engine.setProperty("rate", 170)
                engine.say(text)
                engine.runAndWait()
            except Exception:
                pass
        threading.Thread(target=_speak, daemon=True).start()


# ── Card widget ───────────────────────────────────────────────────────────────
class Card(BoxLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.orientation = "vertical"
        self.padding = [dp(18), dp(14)]
        self.spacing = dp(8)
        with self.canvas.before:
            Color(*C_CARD)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])
            Color(*C_BORDER)
            self._border = Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, dp(14)),
                width=1
            )
        self.bind(pos=self._update, size=self._update)

    def _update(self, *_):
        self._rect.pos  = self.pos
        self._rect.size = self.size
        self._border.rounded_rectangle = (
            self.x, self.y, self.width, self.height, dp(14)
        )


# ── Animated Toggle ───────────────────────────────────────────────────────────
class BuddyToggle(Widget):
    W = dp(58)
    H = dp(30)

    def __init__(self, on_change=None, **kw):
        super().__init__(size_hint=(None, None), size=(self.W, self.H), **kw)
        self._state    = False
        self._progress = 0.0   # 0 = off, 1 = on
        self._on_change = on_change
        self._draw()
        self.bind(on_touch_up=self._touch)

    def _touch(self, _, touch):
        if self.collide_point(*touch.pos):
            self.toggle()

    def toggle(self):
        self._state = not self._state
        if self._on_change:
            self._on_change(self._state)
        target = 1.0 if self._state else 0.0
        anim = Animation(_progress=target, duration=0.2)
        anim.bind(on_progress=lambda *_: self._draw())
        anim.bind(on_complete=lambda *_: self._draw())
        anim.start(self)

    def set(self, value):
        if value != self._state:
            self._state = value
            self._progress = 1.0 if value else 0.0
            self._draw()

    def get(self):
        return self._state

    def _draw(self, *_):
        self.canvas.clear()
        t  = self._progress
        # interpolate track color: dim → accent
        r = 0.18 + t * (0.42 - 0.18)
        g = 0.18 + t * (0.39 - 0.18)
        b = 0.25 + t * (1.00 - 0.25)
        with self.canvas:
            Color(r, g, b, 1)
            RoundedRectangle(pos=self.pos, size=(self.W, self.H), radius=[self.H / 2])
            # thumb
            pad    = dp(3)
            travel = self.W - self.H
            cx = self.x + pad + (self.H / 2 - pad) + t * travel
            cy = self.y + self.H / 2
            R  = self.H / 2 - dp(3)
            Color(0.93, 0.93, 0.96, 1)
            Ellipse(pos=(cx - R, cy - R), size=(R * 2, R * 2))


# ── Toast Popup ───────────────────────────────────────────────────────────────
class BuddyToast(Popup):
    def __init__(self, message, duration=2.5, **kw):
        content = BoxLayout(
            orientation="horizontal",
            padding=[dp(16), dp(12)],
            spacing=dp(12)
        )
        with content.canvas.before:
            Color(*C_CARD)
            self._bg = RoundedRectangle(radius=[dp(14)])
        content.bind(
            pos=lambda w, _: setattr(self._bg, "pos",  w.pos),
            size=lambda w, _: setattr(self._bg, "size", w.size),
        )
        icon = Label(
            text="🤖",
            font_size=dp(26),
            size_hint=(None, 1),
            width=dp(40)
        )
        msg = Label(
            text=message,
            font_size=dp(15),
            color=C_PRI,
            bold=True,
            text_size=(dp(200), None),
            halign="left",
            valign="middle"
        )
        content.add_widget(icon)
        content.add_widget(msg)

        super().__init__(
            title="",
            content=content,
            size_hint=(None, None),
            size=(dp(280), dp(80)),
            separator_height=0,
            background="",
            background_color=(0, 0, 0, 0),
            **kw
        )
        Clock.schedule_once(lambda dt: self.dismiss(), duration)

    def open(self, *args):
        super().open(*args)


# ── Pulse Mic Widget ──────────────────────────────────────────────────────────
class PulseWidget(Widget):
    def __init__(self, **kw):
        super().__init__(size_hint=(None, None), size=(dp(110), dp(110)), **kw)
        self._phase   = 0.0
        self._running = False
        self._event   = None
        self._draw_idle()

    def start(self):
        self._running = True
        self._event = Clock.schedule_interval(self._animate, 1 / 20)

    def stop(self):
        self._running = False
        if self._event:
            self._event.cancel()
        self._draw_idle()

    def _draw_idle(self):
        self.canvas.clear()
        cx = self.center_x
        cy = self.center_y
        R  = dp(30)
        with self.canvas:
            Color(*C_SURFACE)
            Ellipse(pos=(cx - R, cy - R), size=(R * 2, R * 2))
            Color(*C_ACCENT)
            Line(circle=(cx, cy, R), width=dp(1.5))
        self._draw_mic(cx, cy)

    def _animate(self, dt):
        import math
        self.canvas.clear()
        cx = self.center_x
        cy = self.center_y
        with self.canvas:
            for i in range(3, 0, -1):
                r = dp(28 + i * 14)
                alpha = 0.08 + 0.06 * math.sin(self._phase + i)
                Color(0.42, 0.39, 1.0, alpha)
                Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))
            Color(*C_ACCENT)
            R = dp(30)
            Ellipse(pos=(cx - R, cy - R), size=(R * 2, R * 2))
        self._draw_mic(cx, cy)
        self._phase += 0.2

    def _draw_mic(self, cx, cy):
        with self.canvas:
            Color(0.93, 0.93, 0.96, 1)
            # mic body
            mw, mh = dp(10), dp(16)
            mx = cx - mw / 2
            my = cy - dp(2)
            RoundedRectangle(
                pos=(mx, my), size=(mw, mh), radius=[mw / 2]
            )
            # mic stand
            Color(0.93, 0.93, 0.96, 0.8)
            Line(
                points=[cx, my - dp(4), cx, my - dp(8)],
                width=dp(1.2)
            )
            Line(
                ellipse=(cx - dp(6), my - dp(10), dp(12), dp(6), 0, 180),
                width=dp(1.2)
            )


# ── Main Layout ───────────────────────────────────────────────────────────────
class BuddyLayout(FloatLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._active       = False
        self._awaiting_cmd = False
        self._stop_event   = threading.Event()
        self._build()

    def _build(self):
        scroll = ScrollView(
            pos_hint={"x": 0, "y": 0},
            size_hint=(1, 1),
            do_scroll_x=False
        )

        root = BoxLayout(
            orientation="vertical",
            padding=[dp(22), dp(16)],
            spacing=dp(14),
            size_hint_y=None
        )
        root.bind(minimum_height=root.setter("height"))

        # ── Status bar ────────────────────────────────────────────────────────
        sb = BoxLayout(size_hint_y=None, height=dp(32))
        sb.add_widget(Label(
            text="9:41",
            font_size=dp(13), bold=True,
            color=C_PRI, halign="left",
            size_hint_x=None, width=dp(60)
        ))
        sb.add_widget(Widget())
        sb.add_widget(Label(
            text="● ● ●",
            font_size=dp(9), color=C_SEC,
            size_hint_x=None, width=dp(60),
            halign="right"
        ))
        root.add_widget(sb)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        hdr.add_widget(Label(
            text="[b]Buddy[/b]",
            markup=True, font_size=dp(30),
            color=C_PRI, halign="left",
            size_hint_x=None, width=dp(110)
        ))
        hdr.add_widget(Label(
            text="Assistant",
            font_size=dp(30), color=C_ACCENT,
            halign="left"
        ))
        root.add_widget(hdr)

        root.add_widget(Label(
            text="Your always-on voice companion",
            font_size=dp(12), color=C_SEC,
            size_hint_y=None, height=dp(24),
            halign="left"
        ))

        # ── Divider ───────────────────────────────────────────────────────────
        div = Widget(size_hint_y=None, height=dp(1))
        with div.canvas:
            Color(*C_BORDER)
            Rectangle(pos=div.pos, size=div.size)
        div.bind(pos=lambda w, _: setattr(
            w.canvas.children[1], "pos", w.pos))
        div.bind(size=lambda w, _: setattr(
            w.canvas.children[1], "size", w.size))
        root.add_widget(div)

        # ── Status card ───────────────────────────────────────────────────────
        status_card = Card(size_hint_y=None, height=dp(80))
        status_top = BoxLayout(size_hint_y=None, height=dp(22))
        status_top.add_widget(Label(
            text="Status", font_size=dp(11),
            color=C_SEC, halign="left"
        ))
        self._status_dot = Label(
            text="●", font_size=dp(14),
            color=C_DIM, halign="right",
            size_hint_x=None, width=dp(30)
        )
        status_top.add_widget(self._status_dot)
        self._status_lbl = Label(
            text="Inactive",
            font_size=dp(20), bold=True,
            color=C_DIM, halign="left",
            size_hint_y=None, height=dp(36)
        )
        status_card.add_widget(status_top)
        status_card.add_widget(self._status_lbl)
        root.add_widget(status_card)

        # ── Toggle card ───────────────────────────────────────────────────────
        toggle_card = Card(size_hint_y=None, height=dp(140))

        # Active row
        row_a = BoxLayout(size_hint_y=None, height=dp(54), spacing=dp(10))
        left_a = BoxLayout(orientation="vertical", spacing=dp(2))
        left_a.add_widget(Label(
            text="⚡  Active",
            font_size=dp(14), bold=True,
            color=C_PRI, halign="left"
        ))
        left_a.add_widget(Label(
            text="Listen in background",
            font_size=dp(11), color=C_SEC, halign="left"
        ))
        self._toggle_active = BuddyToggle(on_change=self._on_active)
        row_a.add_widget(left_a)
        row_a.add_widget(self._toggle_active)
        toggle_card.add_widget(row_a)

        toggle_card.add_widget(Widget(size_hint_y=None, height=dp(8)))

        # Inactive row
        row_i = BoxLayout(size_hint_y=None, height=dp(54), spacing=dp(10))
        left_i = BoxLayout(orientation="vertical", spacing=dp(2))
        left_i.add_widget(Label(
            text="🔇  Inactive",
            font_size=dp(14), bold=True,
            color=C_PRI, halign="left"
        ))
        left_i.add_widget(Label(
            text="Buddy sleeps silently",
            font_size=dp(11), color=C_SEC, halign="left"
        ))
        self._toggle_inactive = BuddyToggle(on_change=self._on_inactive)
        self._toggle_inactive.set(True)
        row_i.add_widget(left_i)
        row_i.add_widget(self._toggle_inactive)
        toggle_card.add_widget(row_i)
        root.add_widget(toggle_card)

        # ── Mic pulse ─────────────────────────────────────────────────────────
        mic_box = BoxLayout(
            orientation="vertical",
            size_hint_y=None, height=dp(150),
            spacing=dp(8)
        )
        pulse_row = BoxLayout(size_hint_y=None, height=dp(110))
        self._pulse = PulseWidget()
        # centre the pulse widget
        spacer_l = Widget()
        spacer_r = Widget()
        pulse_row.add_widget(spacer_l)
        pulse_row.add_widget(self._pulse)
        pulse_row.add_widget(spacer_r)
        mic_box.add_widget(pulse_row)
        mic_box.add_widget(Label(
            text='Say  "Hello Buddy"  to wake up',
            font_size=dp(11), color=C_DIM,
            size_hint_y=None, height=dp(24)
        ))
        root.add_widget(mic_box)

        # ── Log card ──────────────────────────────────────────────────────────
        log_card = Card(size_hint_y=None, height=dp(160))
        log_card.add_widget(Label(
            text="Activity Log",
            font_size=dp(11), color=C_SEC,
            size_hint_y=None, height=dp(20),
            halign="left"
        ))
        self._log_lbl = Label(
            text="App started. Toggle Active to begin listening.",
            font_size=dp(11), color=C_SEC,
            halign="left", valign="top",
            text_size=(Window.width - dp(80), None)
        )
        log_card.add_widget(self._log_lbl)
        root.add_widget(log_card)

        # ── Quick test buttons ────────────────────────────────────────────────
        test_card = Card(size_hint_y=None, height=dp(80))
        test_card.add_widget(Label(
            text="Quick Test (no mic needed)",
            font_size=dp(11), color=C_SEC,
            size_hint_y=None, height=dp(20),
            halign="left"
        ))
        btn_row = BoxLayout(spacing=dp(10), size_hint_y=None, height=dp(40))

        btn_wake = Button(
            text="Say: Hello Buddy",
            font_size=dp(12),
            background_normal="",
            background_color=C_SURFACE,
            color=C_ACCENT,
            bold=True
        )
        btn_wake.bind(on_press=lambda _: self._process(WAKE_WORD))

        btn_wa = Button(
            text="Say: Open WhatsApp",
            font_size=dp(12),
            background_normal="",
            background_color=C_SURFACE,
            color=C_ACCENT,
            bold=True
        )
        btn_wa.bind(on_press=lambda _: self._process(CMD_WA))

        btn_row.add_widget(btn_wake)
        btn_row.add_widget(btn_wa)
        test_card.add_widget(btn_row)
        root.add_widget(test_card)

        # ── Footer ────────────────────────────────────────────────────────────
        root.add_widget(Label(
            text="Buddy  •  v1.0",
            font_size=dp(10), color=C_DIM,
            size_hint_y=None, height=dp(30)
        ))

        scroll.add_widget(root)
        self.add_widget(scroll)

    # ── Toggle logic ──────────────────────────────────────────────────────────
    def _on_active(self, state):
        if state:
            self._active = True
            self._toggle_inactive.set(False)
            self._status_dot.color = C_GREEN
            self._status_lbl.color = C_GREEN
            self._status_lbl.text  = "Active"
            self._start_listener()
        else:
            self._active = False
            self._toggle_inactive.set(True)
            self._status_dot.color = C_DIM
            self._status_lbl.color = C_DIM
            self._status_lbl.text  = "Inactive"
            self._stop_listener()

    def _on_inactive(self, state):
        if state and self._toggle_active.get():
            self._toggle_active.set(False)
        elif not state and not self._toggle_active.get():
            self._toggle_active.set(True)

    # ── Listener ──────────────────────────────────────────────────────────────
    def _start_listener(self):
        self._stop_event.clear()
        threading.Thread(target=self._listen_loop, daemon=True).start()
        self._pulse.start()
        self._log("Listening in background...")

    def _stop_listener(self):
        self._stop_event.set()
        self._pulse.stop()
        self._log("Listener stopped.")

    def _listen_loop(self):
        if not SPEECH_OK:
            Clock.schedule_once(lambda dt: self._log(
                "speech_recognition not installed.\n"
                "Use Quick Test buttons to demo."
            ))
            return
        recognizer = sr.Recognizer()
        recognizer.dynamic_energy_threshold = True
        while not self._stop_event.is_set():
            try:
                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.4)
                    try:
                        audio = recognizer.listen(
                            source, timeout=6, phrase_time_limit=5
                        )
                    except sr.WaitTimeoutError:
                        continue
                if self._stop_event.is_set():
                    break
                try:
                    text = recognizer.recognize_google(audio).lower().strip()
                    Clock.schedule_once(
                        lambda dt, t=text: self._process(t)
                    )
                except sr.UnknownValueError:
                    pass
                except sr.RequestError as e:
                    Clock.schedule_once(
                        lambda dt, e=e: self._log(f"SR error: {e}")
                    )
                    time.sleep(2)
            except Exception as e:
                Clock.schedule_once(
                    lambda dt, e=e: self._log(f"Mic error: {e}")
                )
                time.sleep(2)

    # ── Command processor ─────────────────────────────────────────────────────
    def _process(self, text):
        text = text.lower().strip()
        self._log(f"Heard: {text}")

        if WAKE_WORD in text:
            self._awaiting_cmd = True
            self._show_toast("Yes Buddy! 👋")
            speak_async("Yes Buddy")
            return

        if self._awaiting_cmd:
            if CMD_WA in text:
                self._awaiting_cmd = False
                self._show_toast("Opening WhatsApp... 💬")
                speak_async("Opening WhatsApp")
                threading.Thread(
                    target=self._do_open_wa, daemon=True
                ).start()
            else:
                self._log(f"Unknown command: {text}")

    def _do_open_wa(self):
        ok = open_whatsapp()
        Clock.schedule_once(
            lambda dt: self._log(
                "WhatsApp launched!" if ok else "WhatsApp not found on device."
            )
        )

    # ── UI helpers ────────────────────────────────────────────────────────────
    def _show_toast(self, msg):
        toast = BuddyToast(msg)
        toast.open()

    def _log(self, msg):
        ts = time.strftime("%H:%M:%S")
        self._log_lbl.text = f"[{ts}] {msg}"


# ── App class ─────────────────────────────────────────────────────────────────
class BuddyAssistantApp(App):
    def build(self):
        self.title = "Buddy Assistant"
        return BuddyLayout()


if __name__ == "__main__":
    BuddyAssistantApp().run()