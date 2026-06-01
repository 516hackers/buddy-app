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

# ── Window setup ──────────────────────────────────────────────
Window.clearcolor = (0.04, 0.04, 0.06, 1)

# ── Optional imports ──────────────────────────────────────────
try:
    import speech_recognition as sr
    SPEECH_OK = True
except Exception:
    SPEECH_OK = False

try:
    import pyttsx3
    TTS_OK = True
except Exception:
    TTS_OK = False

# ── Colors ────────────────────────────────────────────────────
C_BG      = (0.04, 0.04, 0.06, 1)
C_CARD    = (0.07, 0.07, 0.10, 1)
C_SURFACE = (0.10, 0.10, 0.15, 1)
C_ACCENT  = (0.42, 0.39, 1.00, 1)
C_GREEN   = (0.26, 0.91, 0.48, 1)
C_DIM     = (0.27, 0.27, 0.40, 1)
C_SEC     = (0.53, 0.53, 0.67, 1)
C_PRI     = (0.93, 0.93, 0.96, 1)
C_BORDER  = (0.16, 0.16, 0.24, 1)

WAKE_WORD = "hello buddy"
CMD_WA    = "open whatsapp"


def open_whatsapp():
    try:
        subprocess.Popen(
            ["am", "start", "-n", "com.whatsapp/.Main"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except Exception:
        try:
            subprocess.Popen(
                ["am", "start", "-a", "android.intent.action.VIEW",
                 "-d", "whatsapp://"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
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


class Card(BoxLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.orientation = "vertical"
        self.padding = [dp(16), dp(12)]
        self.spacing = dp(8)
        with self.canvas.before:
            Color(*C_CARD)
            self._rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[dp(12)]
            )
        self.bind(pos=self._update, size=self._update)

    def _update(self, *_):
        self._rect.pos  = self.pos
        self._rect.size = self.size


class BuddyToggle(Widget):
    def __init__(self, on_change=None, **kw):
        super().__init__(
            size_hint=(None, None),
            size=(dp(56), dp(28)),
            **kw
        )
        self._state     = False
        self._progress  = 0.0
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
        anim = Animation(_progress=target, duration=0.18)
        anim.bind(on_progress=lambda *_: self._draw())
        anim.bind(on_complete=lambda *_: self._draw())
        anim.start(self)

    def set(self, value):
        if value != self._state:
            self._state   = value
            self._progress = 1.0 if value else 0.0
            self._draw()

    def get(self):
        return self._state

    def _draw(self, *_):
        self.canvas.clear()
        t = self._progress
        r = 0.18 + t * (0.42 - 0.18)
        g = 0.18 + t * (0.39 - 0.18)
        b = 0.25 + t * (1.00 - 0.25)
        W, H = self.width, self.height
        with self.canvas:
            Color(r, g, b, 1)
            RoundedRectangle(
                pos=self.pos, size=(W, H), radius=[H / 2]
            )
            pad    = dp(3)
            travel = W - H
            cx = self.x + H / 2 + t * travel
            cy = self.y + H / 2
            R  = H / 2 - dp(3)
            Color(0.93, 0.93, 0.96, 1)
            Ellipse(pos=(cx - R, cy - R), size=(R * 2, R * 2))


class BuddyToast(Popup):
    def __init__(self, message, duration=2.5, **kw):
        content = BoxLayout(
            orientation="horizontal",
            padding=[dp(14), dp(10)],
            spacing=dp(10)
        )
        with content.canvas.before:
            Color(*C_CARD)
            self._bg = RoundedRectangle(radius=[dp(12)])
        content.bind(
            pos =lambda w, _: setattr(self._bg, "pos",  w.pos),
            size=lambda w, _: setattr(self._bg, "size", w.size),
        )
        icon = Label(
            text="🤖",
            font_size=dp(24),
            size_hint=(None, 1),
            width=dp(36)
        )
        msg = Label(
            text=message,
            font_size=dp(14),
            color=C_PRI,
            bold=True,
            text_size=(dp(190), None),
            halign="left",
            valign="middle"
        )
        content.add_widget(icon)
        content.add_widget(msg)
        super().__init__(
            title="",
            content=content,
            size_hint=(None, None),
            size=(dp(270), dp(76)),
            separator_height=0,
            background="",
            background_color=(0, 0, 0, 0),
            **kw
        )
        Clock.schedule_once(lambda dt: self.dismiss(), duration)


class PulseWidget(Widget):
    def __init__(self, **kw):
        super().__init__(
            size_hint=(None, None),
            size=(dp(100), dp(100)),
            **kw
        )
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
        cx, cy = self.center_x, self.center_y
        R = dp(28)
        with self.canvas:
            Color(*C_SURFACE)
            Ellipse(pos=(cx - R, cy - R), size=(R * 2, R * 2))
            Color(*C_ACCENT)
            Line(circle=(cx, cy, R), width=dp(1.5))
            Color(0.93, 0.93, 0.96, 1)
            mw, mh = dp(9), dp(14)
            RoundedRectangle(
                pos=(cx - mw/2, cy - dp(1)),
                size=(mw, mh),
                radius=[mw / 2]
            )

    def _animate(self, dt):
        import math
        self.canvas.clear()
        cx, cy = self.center_x, self.center_y
        with self.canvas:
            for i in range(3, 0, -1):
                r = dp(26 + i * 12)
                alpha = 0.07 + 0.05 * math.sin(self._phase + i)
                Color(0.42, 0.39, 1.0, alpha)
                Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))
            Color(*C_ACCENT)
            R = dp(28)
            Ellipse(pos=(cx - R, cy - R), size=(R * 2, R * 2))
            Color(0.93, 0.93, 0.96, 1)
            mw, mh = dp(9), dp(14)
            RoundedRectangle(
                pos=(cx - mw/2, cy - dp(1)),
                size=(mw, mh),
                radius=[mw / 2]
            )
        self._phase += 0.2


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
            padding=[dp(20), dp(14)],
            spacing=dp(12),
            size_hint_y=None
        )
        root.bind(minimum_height=root.setter("height"))

        # Status bar
        sb = BoxLayout(size_hint_y=None, height=dp(30))
        sb.add_widget(Label(
            text="9:41", font_size=dp(12), bold=True,
            color=C_PRI, halign="left",
            size_hint_x=None, width=dp(50)
        ))
        sb.add_widget(Widget())
        sb.add_widget(Label(
            text="● ● ●", font_size=dp(9), color=C_SEC,
            size_hint_x=None, width=dp(50), halign="right"
        ))
        root.add_widget(sb)

        # Header
        hdr = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        hdr.add_widget(Label(
            text="[b]Buddy[/b]", markup=True,
            font_size=dp(28), color=C_PRI,
            halign="left", size_hint_x=None, width=dp(105)
        ))
        hdr.add_widget(Label(
            text="Assistant", font_size=dp(28),
            color=C_ACCENT, halign="left"
        ))
        root.add_widget(hdr)

        root.add_widget(Label(
            text="Your always-on voice companion",
            font_size=dp(12), color=C_SEC,
            size_hint_y=None, height=dp(22), halign="left"
        ))

        # Divider
        div = Widget(size_hint_y=None, height=dp(1))
        with div.canvas:
            Color(*C_BORDER)
            self._div_rect = Rectangle(pos=div.pos, size=div.size)
        div.bind(
            pos =lambda w, v: setattr(self._div_rect, "pos",  v),
            size=lambda w, v: setattr(self._div_rect, "size", v)
        )
        root.add_widget(div)

        # Status card
        sc = Card(size_hint_y=None, height=dp(76))
        st = BoxLayout(size_hint_y=None, height=dp(20))
        st.add_widget(Label(
            text="Status", font_size=dp(11),
            color=C_SEC, halign="left"
        ))
        self._status_dot = Label(
            text="●", font_size=dp(13), color=C_DIM,
            halign="right", size_hint_x=None, width=dp(28)
        )
        st.add_widget(self._status_dot)
        self._status_lbl = Label(
            text="Inactive", font_size=dp(20), bold=True,
            color=C_DIM, halign="left",
            size_hint_y=None, height=dp(34)
        )
        sc.add_widget(st)
        sc.add_widget(self._status_lbl)
        root.add_widget(sc)

        # Toggle card
        tc = Card(size_hint_y=None, height=dp(136))

        row_a = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        la = BoxLayout(orientation="vertical", spacing=dp(2))
        la.add_widget(Label(
            text="⚡  Active", font_size=dp(14), bold=True,
            color=C_PRI, halign="left"
        ))
        la.add_widget(Label(
            text="Listen in background",
            font_size=dp(11), color=C_SEC, halign="left"
        ))
        self._toggle_active = BuddyToggle(on_change=self._on_active)
        row_a.add_widget(la)
        row_a.add_widget(self._toggle_active)
        tc.add_widget(row_a)
        tc.add_widget(Widget(size_hint_y=None, height=dp(6)))

        row_i = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        li = BoxLayout(orientation="vertical", spacing=dp(2))
        li.add_widget(Label(
            text="🔇  Inactive", font_size=dp(14), bold=True,
            color=C_PRI, halign="left"
        ))
        li.add_widget(Label(
            text="Buddy sleeps silently",
            font_size=dp(11), color=C_SEC, halign="left"
        ))
        self._toggle_inactive = BuddyToggle(on_change=self._on_inactive)
        self._toggle_inactive.set(True)
        row_i.add_widget(li)
        row_i.add_widget(self._toggle_inactive)
        tc.add_widget(row_i)
        root.add_widget(tc)

        # Mic pulse
        mic_box = BoxLayout(
            orientation="vertical",
            size_hint_y=None, height=dp(140), spacing=dp(6)
        )
        pulse_row = BoxLayout(size_hint_y=None, height=dp(106))
        self._pulse = PulseWidget()
        pulse_row.add_widget(Widget())
        pulse_row.add_widget(self._pulse)
        pulse_row.add_widget(Widget())
        mic_box.add_widget(pulse_row)
        mic_box.add_widget(Label(
            text='Say  "Hello Buddy"  to wake up',
            font_size=dp(11), color=C_DIM,
            size_hint_y=None, height=dp(22)
        ))
        root.add_widget(mic_box)

        # Log card
        lc = Card(size_hint_y=None, height=dp(150))
        lc.add_widget(Label(
            text="Activity Log", font_size=dp(11), color=C_SEC,
            size_hint_y=None, height=dp(18), halign="left"
        ))
        self._log_lbl = Label(
            text="App started. Toggle Active to begin.",
            font_size=dp(11), color=C_SEC,
            halign="left", valign="top",
            text_size=(Window.width - dp(72), None)
        )
        lc.add_widget(self._log_lbl)
        root.add_widget(lc)

        # Quick test card
        qc = Card(size_hint_y=None, height=dp(90))
        qc.add_widget(Label(
            text="Quick Test (no mic needed)",
            font_size=dp(11), color=C_SEC,
            size_hint_y=None, height=dp(18), halign="left"
        ))
        br = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(42))
        b1 = Button(
            text="Hello Buddy", font_size=dp(12),
            background_normal="", background_color=C_SURFACE,
            color=C_ACCENT, bold=True
        )
        b1.bind(on_press=lambda _: self._process(WAKE_WORD))
        b2 = Button(
            text="Open WhatsApp", font_size=dp(12),
            background_normal="", background_color=C_SURFACE,
            color=C_ACCENT, bold=True
        )
        b2.bind(on_press=lambda _: self._process(CMD_WA))
        br.add_widget(b1)
        br.add_widget(b2)
        qc.add_widget(br)
        root.add_widget(qc)

        root.add_widget(Label(
            text="Buddy  •  v1.0",
            font_size=dp(10), color=C_DIM,
            size_hint_y=None, height=dp(28)
        ))

        scroll.add_widget(root)
        self.add_widget(scroll)

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
                self._log(f"Unknown: {text}")

    def _do_open_wa(self):
        ok = open_whatsapp()
        Clock.schedule_once(
            lambda dt: self._log(
                "WhatsApp launched!" if ok
                else "WhatsApp not found."
            )
        )

    def _show_toast(self, msg):
        BuddyToast(msg).open()

    def _log(self, msg):
        ts = time.strftime("%H:%M:%S")
        self._log_lbl.text = f"[{ts}] {msg}"


class BuddyAssistantApp(App):
    def build(self):
        self.title = "Buddy Assistant"
        try:
            return BuddyLayout()
        except Exception as e:
            from kivy.uix.label import Label
            return Label(
                text=f"Error: {e}",
                color=(1, 0, 0, 1)
            )


if __name__ == "__main__":
    BuddyAssistantApp().run()
