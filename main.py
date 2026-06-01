
import threading
import subprocess
import time
import os

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.popup import Popup
from kivy.graphics import (Color, RoundedRectangle,
                            Rectangle, Ellipse, Line)
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.animation import Animation

# ── window colour (Android ignores Window.size, that's fine) ──
Window.clearcolor = (0.04, 0.04, 0.06, 1)

# ── safe optional imports ──────────────────────────────────────
try:
    import speech_recognition as sr
    SR_OK = True
except Exception:
    SR_OK = False

# ── palette ───────────────────────────────────────────────────
BG      = (0.04, 0.04, 0.06, 1)
CARD    = (0.09, 0.09, 0.13, 1)
SURF    = (0.13, 0.13, 0.18, 1)
ACCENT  = (0.42, 0.38, 1.00, 1)
GREEN   = (0.20, 0.85, 0.45, 1)
DIM     = (0.28, 0.28, 0.40, 1)
SEC     = (0.55, 0.55, 0.68, 1)
PRI     = (0.92, 0.92, 0.96, 1)
BORDER  = (0.18, 0.18, 0.26, 1)

WAKE = "hello buddy"
CMD_WA = "open whatsapp"


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════
def launch_whatsapp():
    """Try every known way to open WhatsApp on Android."""
    cmds = [
        ["am", "start", "-n", "com.whatsapp/.Main"],
        ["am", "start", "-a", "android.intent.action.VIEW",
         "-d", "whatsapp://"],
        ["am", "start", "-n",
         "com.whatsapp.w4b/.Main"],          # WhatsApp Business
    ]
    for cmd in cmds:
        try:
            r = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=4
            )
            if r.returncode == 0:
                return True
        except Exception:
            pass
    return False


# ══════════════════════════════════════════════════════════════
#  CARD  (rounded dark container)
# ══════════════════════════════════════════════════════════════
class Card(BoxLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.orientation = "vertical"
        self.padding     = [dp(16), dp(12), dp(16), dp(12)]
        self.spacing     = dp(6)
        with self.canvas.before:
            Color(*CARD)
            self._bg = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[dp(14)]
            )
            Color(*BORDER)
            self._bd = Line(
                rounded_rectangle=(
                    self.x, self.y,
                    self.width, self.height, dp(14)
                ),
                width=dp(0.8)
            )
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._bg.pos  = self.pos
        self._bg.size = self.size
        self._bd.rounded_rectangle = (
            self.x, self.y, self.width, self.height, dp(14)
        )


# ══════════════════════════════════════════════════════════════
#  ANIMATED TOGGLE
# ══════════════════════════════════════════════════════════════
class Toggle(Widget):
    W = dp(54)
    H = dp(28)

    def __init__(self, callback=None, **kw):
        super().__init__(
            size_hint=(None, None),
            size=(self.W, self.H), **kw
        )
        self._on       = False
        self._prog     = 0.0
        self._callback = callback
        self._anim     = None
        self._draw()
        self.bind(on_touch_up=self._touch)

    # ── public ────────────────────────────────────────────────
    def set_state(self, value, silent=False):
        """Set toggle state; silent=True skips callback."""
        if value == self._on:
            return
        self._on = value
        if not silent and self._callback:
            self._callback(value)
        self._run_anim()

    @property
    def is_on(self):
        return self._on

    # ── internal ──────────────────────────────────────────────
    def _touch(self, _, touch):
        if self.collide_point(*touch.pos):
            self._on = not self._on
            if self._callback:
                self._callback(self._on)
            self._run_anim()

    def _run_anim(self):
        if self._anim:
            self._anim.cancel(self)
        target = 1.0 if self._on else 0.0
        self._anim = Animation(_prog=target, duration=0.18)
        self._anim.bind(
            on_progress=lambda *_: self._draw(),
            on_complete=lambda *_: self._draw()
        )
        self._anim.start(self)

    def _draw(self, *_):
        self.canvas.clear()
        t  = self._prog
        rr = 0.18 + t * (0.42 - 0.18)
        gg = 0.18 + t * (0.38 - 0.18)
        bb = 0.26 + t * (1.00 - 0.26)
        W, H = self.width, self.height
        with self.canvas:
            Color(rr, gg, bb, 1)
            RoundedRectangle(
                pos=self.pos,
                size=(W, H),
                radius=[H / 2]
            )
            pad    = dp(3)
            travel = W - H
            cx     = self.x + H / 2 + t * travel
            cy     = self.y + H / 2
            R      = H / 2 - dp(3)
            Color(0.95, 0.95, 0.97, 1)
            Ellipse(
                pos=(cx - R, cy - R),
                size=(R * 2, R * 2)
            )


# ══════════════════════════════════════════════════════════════
#  TOAST  (floating popup)
# ══════════════════════════════════════════════════════════════
class Toast(Popup):
    def __init__(self, msg, dur=2.5, **kw):
        row = BoxLayout(
            orientation="horizontal",
            padding=[dp(14), dp(10)],
            spacing=dp(10)
        )
        with row.canvas.before:
            Color(*CARD)
            self._bg = RoundedRectangle(radius=[dp(14)])
        row.bind(
            pos =lambda w, v: setattr(self._bg, "pos",  v),
            size=lambda w, v: setattr(self._bg, "size", v)
        )
        # robot emoji as text (always renders on Android)
        row.add_widget(Label(
            text="[b]:)[/b]",
            markup=True,
            font_size=dp(20),
            color=ACCENT,
            size_hint=(None, 1),
            width=dp(34)
        ))
        row.add_widget(Label(
            text=msg,
            font_size=dp(14),
            color=PRI,
            bold=True,
            text_size=(dp(200), None),
            halign="left",
            valign="middle"
        ))
        super().__init__(
            title="",
            content=row,
            size_hint=(None, None),
            size=(dp(260), dp(72)),
            separator_height=0,
            background="",
            background_color=(0, 0, 0, 0),
            **kw
        )
        Clock.schedule_once(lambda dt: self.dismiss(), dur)


# ══════════════════════════════════════════════════════════════
#  PULSE MIC WIDGET
# ══════════════════════════════════════════════════════════════
class Pulse(Widget):
    def __init__(self, **kw):
        super().__init__(
            size_hint=(None, None),
            size=(dp(96), dp(96)), **kw
        )
        self._phase   = 0.0
        self._running = False
        self._ev      = None
        self._idle()

    def start(self):
        if self._running:
            return
        self._running = True
        self._ev = Clock.schedule_interval(self._tick, 1 / 20)

    def stop(self):
        self._running = False
        if self._ev:
            self._ev.cancel()
            self._ev = None
        self._idle()

    def _idle(self):
        self.canvas.clear()
        cx, cy = self.center_x, self.center_y
        R = dp(26)
        with self.canvas:
            Color(*SURF)
            Ellipse(pos=(cx - R, cy - R), size=(R * 2, R * 2))
            Color(*ACCENT)
            Line(circle=(cx, cy, R - dp(1)), width=dp(1.4))
            # mic body (simple rectangle + stand lines)
            Color(*PRI)
            mw, mh = dp(8), dp(13)
            RoundedRectangle(
                pos=(cx - mw / 2, cy),
                size=(mw, mh),
                radius=[mw / 2]
            )
            # stand
            Line(
                points=[cx, cy - dp(1), cx, cy - dp(6)],
                width=dp(1.1)
            )
            Line(
                ellipse=(cx - dp(5), cy - dp(8),
                         dp(10), dp(5), 0, 180),
                width=dp(1.1)
            )

    def _tick(self, dt):
        import math
        self.canvas.clear()
        cx, cy = self.center_x, self.center_y
        with self.canvas:
            for i in range(3, 0, -1):
                r = dp(24 + i * 11)
                a = 0.06 + 0.05 * math.sin(self._phase + i)
                Color(0.42, 0.38, 1.0, a)
                Ellipse(
                    pos=(cx - r, cy - r),
                    size=(r * 2, r * 2)
                )
            Color(*ACCENT)
            R = dp(26)
            Ellipse(pos=(cx - R, cy - R), size=(R * 2, R * 2))
            Color(*PRI)
            mw, mh = dp(8), dp(13)
            RoundedRectangle(
                pos=(cx - mw / 2, cy),
                size=(mw, mh),
                radius=[mw / 2]
            )
            Line(
                points=[cx, cy - dp(1), cx, cy - dp(6)],
                width=dp(1.1)
            )
            Line(
                ellipse=(cx - dp(5), cy - dp(8),
                         dp(10), dp(5), 0, 180),
                width=dp(1.1)
            )
        self._phase += 0.20


# ══════════════════════════════════════════════════════════════
#  MAIN LAYOUT
# ══════════════════════════════════════════════════════════════
class BuddyUI(FloatLayout):

    def __init__(self, **kw):
        super().__init__(**kw)
        self._active   = False
        self._waiting  = False          # awaiting command after wake
        self._stop_ev  = threading.Event()
        self._build()

    # ── build UI ──────────────────────────────────────────────
    def _build(self):
        sv = ScrollView(
            size_hint=(1, 1),
            do_scroll_x=False
        )
        root = BoxLayout(
            orientation="vertical",
            padding=[dp(18), dp(10), dp(18), dp(20)],
            spacing=dp(12),
            size_hint_y=None
        )
        root.bind(minimum_height=root.setter("height"))

        # ── status bar ────────────────────────────────────────
        bar = BoxLayout(size_hint_y=None, height=dp(28))
        bar.add_widget(Label(
            text="Buddy App",
            font_size=dp(11), color=SEC,
            halign="left"
        ))
        bar.add_widget(Label(
            text="v1.0",
            font_size=dp(11), color=DIM,
            halign="right"
        ))
        root.add_widget(bar)

        # ── header ────────────────────────────────────────────
        hdr = BoxLayout(
            size_hint_y=None, height=dp(44),
            spacing=dp(4)
        )
        hdr.add_widget(Label(
            text="[b]Buddy[/b]",
            markup=True,
            font_size=dp(28), color=PRI,
            size_hint_x=None, width=dp(100),
            halign="left"
        ))
        hdr.add_widget(Label(
            text="Assistant",
            font_size=dp(28), color=ACCENT,
            halign="left"
        ))
        root.add_widget(hdr)

        root.add_widget(Label(
            text="Your always-on voice companion",
            font_size=dp(12), color=SEC,
            size_hint_y=None, height=dp(20),
            halign="left"
        ))

        # ── divider ───────────────────────────────────────────
        d = Widget(size_hint_y=None, height=dp(1))
        with d.canvas:
            Color(*BORDER)
            self._div = Rectangle(pos=d.pos, size=d.size)
        d.bind(
            pos =lambda w, v: setattr(self._div, "pos",  v),
            size=lambda w, v: setattr(self._div, "size", v)
        )
        root.add_widget(d)

        # ── status card ───────────────────────────────────────
        sc = Card(size_hint_y=None, height=dp(78))
        srow = BoxLayout(size_hint_y=None, height=dp(22))
        srow.add_widget(Label(
            text="Status",
            font_size=dp(11), color=SEC,
            halign="left"
        ))
        self._dot = Label(
            text="●", font_size=dp(14), color=DIM,
            size_hint_x=None, width=dp(26),
            halign="right"
        )
        srow.add_widget(self._dot)
        self._stat = Label(
            text="Inactive",
            font_size=dp(19), bold=True, color=DIM,
            halign="left",
            size_hint_y=None, height=dp(34)
        )
        sc.add_widget(srow)
        sc.add_widget(self._stat)
        root.add_widget(sc)

        # ── toggle card ───────────────────────────────────────
        tc = Card(size_hint_y=None, height=dp(144))

        # Active row
        ra = BoxLayout(
            size_hint_y=None, height=dp(56),
            spacing=dp(10)
        )
        la = BoxLayout(orientation="vertical", spacing=dp(2))
        la.add_widget(Label(
            text="Active  [Listen]",
            font_size=dp(14), bold=True, color=PRI,
            halign="left"
        ))
        la.add_widget(Label(
            text="Tap to start background listener",
            font_size=dp(10), color=SEC,
            halign="left"
        ))
        self._tog_active = Toggle(callback=self._on_active_tap)
        ra.add_widget(la)
        ra.add_widget(self._tog_active)
        tc.add_widget(ra)

        tc.add_widget(Widget(size_hint_y=None, height=dp(6)))

        # Inactive row
        ri = BoxLayout(
            size_hint_y=None, height=dp(56),
            spacing=dp(10)
        )
        li = BoxLayout(orientation="vertical", spacing=dp(2))
        li.add_widget(Label(
            text="Inactive  [Sleep]",
            font_size=dp(14), bold=True, color=PRI,
            halign="left"
        ))
        li.add_widget(Label(
            text="Buddy sleeps, no mic access",
            font_size=dp(10), color=SEC,
            halign="left"
        ))
        self._tog_inactive = Toggle(callback=self._on_inactive_tap)
        self._tog_inactive.set_state(True, silent=True)
        ri.add_widget(li)
        ri.add_widget(self._tog_inactive)
        tc.add_widget(ri)
        root.add_widget(tc)

        # ── pulse mic ─────────────────────────────────────────
        mb = BoxLayout(
            orientation="vertical",
            size_hint_y=None, height=dp(136),
            spacing=dp(6)
        )
        pr = BoxLayout(size_hint_y=None, height=dp(100))
        self._pulse = Pulse()
        pr.add_widget(Widget())
        pr.add_widget(self._pulse)
        pr.add_widget(Widget())
        mb.add_widget(pr)
        self._hint = Label(
            text='Say "Hello Buddy" to wake up',
            font_size=dp(11), color=DIM,
            size_hint_y=None, height=dp(22)
        )
        mb.add_widget(self._hint)
        root.add_widget(mb)

        # ── log card ──────────────────────────────────────────
        lc = Card(size_hint_y=None, height=dp(148))
        lc.add_widget(Label(
            text="Activity Log",
            font_size=dp(11), color=SEC,
            size_hint_y=None, height=dp(18),
            halign="left"
        ))
        self._log = Label(
            text="App ready. Toggle Active to start.",
            font_size=dp(11), color=SEC,
            halign="left", valign="top",
            text_size=(Window.width - dp(56), None)
        )
        lc.add_widget(self._log)
        root.add_widget(lc)

        # ── quick test card ───────────────────────────────────
        qc = Card(size_hint_y=None, height=dp(110))
        qc.add_widget(Label(
            text="Quick Test  (works without mic)",
            font_size=dp(11), color=SEC,
            size_hint_y=None, height=dp(18),
            halign="left"
        ))

        b1 = Button(
            text='1. Say: "Hello Buddy"',
            font_size=dp(12),
            background_normal="",
            background_color=SURF,
            color=ACCENT,
            bold=True,
            size_hint_y=None,
            height=dp(38)
        )
        b1.bind(on_release=lambda _: self._process(WAKE))

        b2 = Button(
            text='2. Say: "Open WhatsApp"',
            font_size=dp(12),
            background_normal="",
            background_color=SURF,
            color=ACCENT,
            bold=True,
            size_hint_y=None,
            height=dp(38)
        )
        b2.bind(on_release=lambda _: self._process(CMD_WA))

        qc.add_widget(b1)
        qc.add_widget(b2)
        root.add_widget(qc)

        # ── how to use card ───────────────────────────────────
        hc = Card(size_hint_y=None, height=dp(130))
        hc.add_widget(Label(
            text="How to use",
            font_size=dp(11), color=SEC,
            size_hint_y=None, height=dp(18),
            halign="left"
        ))
        steps = [
            "1. Toggle Active ON",
            "2. Say  Hello Buddy",
            "3. Wait for popup  Yes Buddy",
            "4. Say  Open WhatsApp",
        ]
        for s in steps:
            hc.add_widget(Label(
                text=s,
                font_size=dp(11), color=PRI,
                size_hint_y=None, height=dp(20),
                halign="left"
            ))
        root.add_widget(hc)

        root.add_widget(Label(
            text="Buddy Assistant  v1.0",
            font_size=dp(10), color=DIM,
            size_hint_y=None, height=dp(28)
        ))

        sv.add_widget(root)
        self.add_widget(sv)

    # ══════════════════════════════════════════════════════════
    #  TOGGLE CALLBACKS
    # ══════════════════════════════════════════════════════════
    def _on_active_tap(self, state):
        if state:
            # turn inactive OFF silently
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
        self._dot.color  = GREEN
        self._stat.color = GREEN
        self._stat.text  = "Active — Listening"
        self._hint.text  = 'Say "Hello Buddy" to wake up'
        self._pulse.start()
        self._stop_ev.clear()
        t = threading.Thread(
            target=self._listen_loop,
            daemon=True
        )
        t.start()
        self._write_log("Listener started")

    def _deactivate(self):
        self._active  = False
        self._waiting = False
        self._stop_ev.set()
        self._dot.color  = DIM
        self._stat.color = DIM
        self._stat.text  = "Inactive"
        self._hint.text  = 'Toggle Active to begin'
        self._pulse.stop()
        self._write_log("Listener stopped")

    # ══════════════════════════════════════════════════════════
    #  VOICE LISTENER LOOP
    # ══════════════════════════════════════════════════════════
    def _listen_loop(self):
        if not SR_OK:
            Clock.schedule_once(lambda dt: self._write_log(
                "speech_recognition not installed\n"
                "Use Quick Test buttons instead"
            ))
            return

        rec = sr.Recognizer()
        rec.dynamic_energy_threshold = True
        rec.energy_threshold = 300
        rec.pause_threshold  = 0.8

        while not self._stop_ev.is_set():
            try:
                with sr.Microphone() as src:
                    rec.adjust_for_ambient_noise(src, duration=0.5)
                    Clock.schedule_once(
                        lambda dt: self._write_log("Listening...")
                    )
                    try:
                        audio = rec.listen(
                            src,
                            timeout=8,
                            phrase_time_limit=6
                        )
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
                        lambda dt, e=e: self._write_log(
                            f"Speech API error: {e}"
                        )
                    )
                    time.sleep(3)

            except OSError as e:
                Clock.schedule_once(
                    lambda dt, e=e: self._write_log(
                        f"Mic unavailable: {e}"
                    )
                )
                time.sleep(4)
            except Exception as e:
                Clock.schedule_once(
                    lambda dt, e=e: self._write_log(f"Error: {e}")
                )
                time.sleep(2)

    # ══════════════════════════════════════════════════════════
    #  COMMAND PROCESSOR
    # ══════════════════════════════════════════════════════════
    def _on_heard(self, text):
        self._write_log(f'Heard: "{text}"')
        self._process(text)

    def _process(self, text):
        text = text.lower().strip()

        if WAKE in text:
            self._waiting = True
            self._show_toast("Yes Buddy!")
            self._write_log("Wake word detected - awaiting command")
            self._hint.text = 'Now say "Open WhatsApp"'
            return

        if self._waiting:
            if CMD_WA in text:
                self._waiting = False
                self._show_toast("Opening WhatsApp...")
                self._write_log("Opening WhatsApp...")
                self._hint.text = 'Say "Hello Buddy" to wake up'
                threading.Thread(
                    target=self._open_wa,
                    daemon=True
                ).start()
            else:
                self._write_log(f'Unknown command: "{text}"')
                self._hint.text = 'Say "Hello Buddy" to wake up'
                self._waiting = False

    def _open_wa(self):
        ok = launch_whatsapp()
        Clock.schedule_once(
            lambda dt: self._write_log(
                "WhatsApp opened!" if ok
                else "WhatsApp not found on device"
            )
        )

    # ══════════════════════════════════════════════════════════
    #  UI UTILITIES
    # ══════════════════════════════════════════════════════════
    def _show_toast(self, msg):
        try:
            Toast(msg).open()
        except Exception as e:
            self._write_log(f"Toast error: {e}")

    def _write_log(self, msg):
        ts = time.strftime("%H:%M:%S")
        self._log.text = f"[{ts}]  {msg}"


# ══════════════════════════════════════════════════════════════
#  APP ENTRY POINT
# ══════════════════════════════════════════════════════════════
class BuddyAssistantApp(App):
    def build(self):
        self.title = "Buddy Assistant"
        try:
            return BuddyUI()
        except Exception as e:
            return Label(
                text=f"Startup error:\n{e}",
                color=(1, 0.3, 0.3, 1),
                font_size=dp(13),
                halign="center"
            )

    def on_stop(self):
        # clean up listener thread on exit
        try:
            self.root._stop_ev.set()
        except Exception:
            pass


if __name__ == "__main__":
    BuddyAssistantApp().run()
ENDOFFILE
python3 -c "
import ast
with open('/home/claude/main.py') as f:
    src = f.read()
ast.parse(src)
print('Syntax OK -', len(src.splitlines()), 'lines')
"a
