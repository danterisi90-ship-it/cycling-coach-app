"""
Coach App — Kivy UI (v2)
=========================
Redesigned for minimal daily friction:

  Screen 1 (HomeScreen):
    - Shows yesterday's stored history (Lag_1/2/3) as read-only badges
    - "Yesterday's ride was:" → 3 large tap-buttons (Rest / Easy / Hard)
    - Tapping a button commits that choice to FIFO storage, advances lags,
      and navigates to the wellness input screen

  Screen 2 (WellnessScreen):
    - Scrollable inputs for morning metrics (SHAP-selected, no action fields)
    - "GET RECOMMENDATION" button → runs simulation → goes to results

  Screen 3 (ResultScreen):
    - Shows 3 scenario cards (Rest / Easy / Hard) with predicted EF slopes
    - Highlights the recommended action
    - "← New Assessment" returns to HomeScreen

Run on PC:
  python app/main.py

Build APK:
  See BUILD_INSTRUCTIONS.md
"""

import os
import sys
import traceback

# -----------------------------------------------------------------------
# EARLY DIAGNOSTIC LOG — runs before any kivy import
# Writes to Android Downloads folder so we can read it via file manager
# -----------------------------------------------------------------------
_LOG_PATHS = [
    '/storage/emulated/0/Download/coach_crash.log',
    '/storage/emulated/0/coach_crash.log',
    os.path.join(os.environ.get('ANDROID_PRIVATE', ''),
                 'coach_crash.log') if os.environ.get('ANDROID_PRIVATE') else None,
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'crash.log'),
]
_LOG_PATHS = [p for p in _LOG_PATHS if p]
_ACTIVE_LOG = None

def _log(msg: str):
    global _ACTIVE_LOG
    line = msg + '\n'
    if _ACTIVE_LOG:
        try:
            with open(_ACTIVE_LOG, 'a') as _f:
                _f.write(line)
            return
        except Exception:
            _ACTIVE_LOG = None
    for p in _LOG_PATHS:
        try:
            with open(p, 'a') as _f:
                _f.write(line)
            _ACTIVE_LOG = p
            return
        except Exception:
            continue

_log('=== COACH APP START ===')
_log(f'Python {sys.version}')
_log(f'CWD: {os.getcwd()}')
_log(f'ANDROID_PRIVATE: {os.environ.get("ANDROID_PRIVATE", "not set")}')
_log(f'Script: {os.path.abspath(__file__)}')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_log('importing kivy...')
from kivy.app import App
from kivy.metrics import dp, sp
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.scrollview import ScrollView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.utils import get_color_from_hex
_log('kivy imported OK')

import traceback

_log('importing coach_engine...')
try:
    from coach_engine import CoachEngine, get_history_labels, ACTION_DECODE, ACTION_ENCODE
    ENGINE_IMPORT_ERROR = None
    _log('coach_engine imported OK')
except Exception as e:
    ENGINE_IMPORT_ERROR = traceback.format_exc()
    _log(f'coach_engine FAILED: {ENGINE_IMPORT_ERROR}')
    CoachEngine = None
    def get_history_labels(): return {"yesterday": "?", "2_days_ago": "?", "3_days_ago": "?"}
    ACTION_DECODE = {0: "Rest", 1: "Easy", 2: "Hard"}
    ACTION_ENCODE = {"Rest": 0, "Easy": 1, "Hard": 2}


# ─────────────────────────────────────────────────────────────
#  Colour palette
# ─────────────────────────────────────────────────────────────
BG_DARK      = get_color_from_hex("#0D1117")
BG_CARD      = get_color_from_hex("#161B22")
BG_CARD2     = get_color_from_hex("#1C2128")
BG_HEADER    = get_color_from_hex("#0F1E35")
ACCENT_BLUE  = get_color_from_hex("#58A6FF")
ACCENT_GREEN = get_color_from_hex("#3FB950")
ACCENT_RED   = get_color_from_hex("#F85149")
ACCENT_AMBER = get_color_from_hex("#E3B341")
TEXT_PRIMARY = get_color_from_hex("#E6EDF3")
TEXT_MUTED   = get_color_from_hex("#8B949E")
TEXT_DIM     = get_color_from_hex("#484F58")

ACTION_PALETTE = {
    "Rest": get_color_from_hex("#3FB950"),
    "Easy": get_color_from_hex("#58A6FF"),
    "Hard": get_color_from_hex("#F85149"),
}


# Window.clearcolor is set inside build() — NOT at module level
# (setting it here crashes on Android before the display is ready)



# ─────────────────────────────────────────────────────────────
#  Shared helpers
# ─────────────────────────────────────────────────────────────

def _bg_canvas(widget, color, radius=dp(0)):
    with widget.canvas.before:
        Color(*color)
        rect = RoundedRectangle(pos=widget.pos, size=widget.size,
                                radius=[radius] if radius else [0])
    widget.bind(
        pos=lambda i, v: setattr(rect, "pos", v),
        size=lambda i, v: setattr(rect, "size", v),
    )
    return rect


def make_header(title: str, subtitle: str = "") -> BoxLayout:
    header = BoxLayout(
        orientation="vertical",
        size_hint_y=None,
        height=dp(86),
        padding=[dp(20), dp(12)],
    )
    _bg_canvas(header, (0.06, 0.12, 0.21, 1))

    t = Label(text=title, font_size=sp(21), bold=True,
              color=TEXT_PRIMARY, halign="left",
              size_hint_y=None, height=dp(34))
    t.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))
    header.add_widget(t)

    if subtitle:
        s = Label(text=subtitle, font_size=sp(12), color=TEXT_MUTED,
                  halign="left", size_hint_y=None, height=dp(20))
        s.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))
        header.add_widget(s)

    return header


def make_section_label(text: str) -> Label:
    lbl = Label(
        text=text, font_size=sp(13), bold=True,
        color=ACCENT_BLUE, halign="left",
        size_hint_y=None, height=dp(28),
    )
    lbl.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))
    return lbl


class ActionButton(Button):
    """Large tap button for Rest / Easy / Hard selection."""

    def __init__(self, action: str, selected: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.action = action
        self.text = action.upper()
        self.font_size = sp(17)
        self.bold = True
        self.color = TEXT_PRIMARY
        self.background_color = (0, 0, 0, 0)
        self.size_hint_y = None
        self.height = dp(54)

        base_color = ACTION_PALETTE[action]
        if selected:
            fill = base_color
        else:
            fill = (base_color[0] * 0.25, base_color[1] * 0.25,
                    base_color[2] * 0.25, 0.9)

        with self.canvas.before:
            self._col = Color(*fill)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[dp(10)])
        self.bind(pos=lambda i, v: setattr(self._rect, "pos", v),
                  size=lambda i, v: setattr(self._rect, "size", v))

        self._selected = selected
        self._base = base_color

    def set_selected(self, selected: bool):
        self._selected = selected
        if selected:
            self._col.rgba = self._base
        else:
            c = self._base
            self._col.rgba = (c[0] * 0.25, c[1] * 0.25, c[2] * 0.25, 0.9)


class HistoryBadge(BoxLayout):
    """Read-only badge showing one historical day's action."""

    def __init__(self, day_label: str, action: str, **kwargs):
        super().__init__(orientation="vertical", spacing=dp(2),
                         padding=dp(8), **kwargs)
        self.size_hint_y = None
        self.height = dp(58)

        color = ACTION_PALETTE.get(action, TEXT_MUTED)
        _bg_canvas(self, (color[0]*0.15, color[1]*0.15, color[2]*0.15, 1),
                   radius=dp(8))

        day_lbl = Label(text=day_label, font_size=sp(10), color=TEXT_MUTED,
                        halign="center", size_hint_y=None, height=dp(16))
        day_lbl.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))

        act_lbl = Label(text=action.upper(), font_size=sp(14), bold=True,
                        color=color, halign="center",
                        size_hint_y=None, height=dp(24))
        act_lbl.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))

        self.add_widget(day_lbl)
        self.add_widget(act_lbl)


class StyledInput(BoxLayout):
    """Label + TextInput pair for wellness metrics."""

    def __init__(self, label: str, hint: str = "", default: str = "", **kwargs):
        super().__init__(orientation="vertical", spacing=dp(4), **kwargs)
        self.size_hint_y = None
        self.height = dp(72)

        lbl = Label(text=label, font_size=sp(12), color=TEXT_MUTED,
                    halign="left", size_hint_y=None, height=dp(20))
        lbl.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))

        self.text_input = TextInput(
            text=str(default),
            hint_text=hint,
            font_size=sp(15),
            foreground_color=TEXT_PRIMARY,
            background_color=BG_CARD2,
            cursor_color=ACCENT_BLUE,
            size_hint_y=None,
            height=dp(44),
            padding=[dp(10), dp(10)],
            multiline=False,
        )
        self.add_widget(lbl)
        self.add_widget(self.text_input)

    @property
    def value(self) -> str:
        return self.text_input.text.strip()


class PrimaryButton(Button):
    """Full-width accent button."""

    def __init__(self, text: str, color=None, **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.font_size = sp(15)
        self.bold = True
        self.color = TEXT_PRIMARY
        self.background_color = (0, 0, 0, 0)
        self.size_hint_y = None
        self.height = dp(54)
        fill = color or ACCENT_BLUE
        with self.canvas.before:
            Color(*fill)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])
        self.bind(pos=lambda i, v: setattr(self._rect, "pos", v),
                  size=lambda i, v: setattr(self._rect, "size", v))


# ─────────────────────────────────────────────────────────────
#  Screen 1 — Home: yesterday's action selector
# ─────────────────────────────────────────────────────────────

class HomeScreen(Screen):
    """
    Shows the 3-day history (read-only) and asks for yesterday's action
    via three large action buttons. No manual number entry here.
    """

    def __init__(self, engine, **kwargs):
        super().__init__(**kwargs)
        self.engine = engine
        self._selected_action = None
        self._action_btns: dict[str, ActionButton] = {}
        self._history_row = None
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical")

        # Header
        root.add_widget(make_header(
            "🚴  Cycling Coach",
            "Daily morning training recommendation",
        ))

        # Scroll body
        scroll = ScrollView()
        body = BoxLayout(
            orientation="vertical",
            padding=[dp(16), dp(14)],
            spacing=dp(14),
            size_hint_y=None,
        )
        body.bind(minimum_height=body.setter("height"))

        # ── History row ──
        body.add_widget(make_section_label("📅  Recent Training History"))

        self._history_row = BoxLayout(
            spacing=dp(8), size_hint_y=None, height=dp(68),
        )
        body.add_widget(self._history_row)
        self._refresh_history_row()

        # Divider
        div = Widget(size_hint_y=None, height=dp(1))
        with div.canvas:
            Color(*TEXT_DIM)
            Rectangle(pos=div.pos, size=div.size)
        body.add_widget(div)

        # ── Action selector ──
        body.add_widget(make_section_label("❓  Yesterday's training was:"))

        note = Label(
            text="Tap to select — history updates automatically",
            font_size=sp(11), color=TEXT_DIM, halign="center",
            size_hint_y=None, height=dp(20),
        )
        note.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))
        body.add_widget(note)

        for action in ("Rest", "Easy", "Hard"):
            btn = ActionButton(action=action, selected=False)
            btn.bind(on_release=lambda b, a=action: self._on_action_tap(a))
            self._action_btns[action] = btn
            body.add_widget(btn)

        # Confirmation hint (hidden until selection made)
        self._confirm_lbl = Label(
            text="",
            font_size=sp(12), color=ACCENT_GREEN,
            halign="center", size_hint_y=None, height=dp(26),
        )
        self._confirm_lbl.bind(
            size=lambda i, v: setattr(i, "text_size", (v[0], None))
        )
        body.add_widget(self._confirm_lbl)

        scroll.add_widget(body)
        root.add_widget(scroll)

        # ── Proceed button ──
        self._proceed_btn = PrimaryButton(
            "ENTER TODAY'S METRICS →",
            color=(0.13, 0.22, 0.38, 1),
        )
        self._proceed_btn.bind(on_release=self._on_proceed)
        root.add_widget(self._proceed_btn)

        self.add_widget(root)

    def _refresh_history_row(self):
        self._history_row.clear_widgets()
        labels = get_history_labels()
        for day_label, action_key in [
            ("3 days ago", "3_days_ago"),
            ("2 days ago", "2_days_ago"),
            ("Yesterday",  "yesterday"),
        ]:
            badge = HistoryBadge(
                day_label=day_label,
                action=labels[action_key],
            )
            self._history_row.add_widget(badge)

    def on_enter(self):
        """Refresh history badges every time we come back to this screen."""
        self._selected_action = None
        self._confirm_lbl.text = ""
        for btn in self._action_btns.values():
            btn.set_selected(False)
        self._refresh_history_row()

    def _on_action_tap(self, action: str):
        # Highlight selected button
        self._selected_action = action
        for name, btn in self._action_btns.items():
            btn.set_selected(name == action)

        # Commit to FIFO storage immediately so history row reflects it
        if self.engine and self.engine.loaded:
            updated = self.engine.commit_yesterday_action(action)
        else:
            from coach_engine import advance_history
            updated = advance_history(action)

        self._refresh_history_row()
        self._confirm_lbl.text = f"✓ Recorded: Yesterday = {action}"

    def _on_proceed(self, *args):
        if self._selected_action is None:
            self._confirm_lbl.text = "⚠ Please select yesterday's action first"
            self._confirm_lbl.color = ACCENT_RED
            return
        self.manager.transition = SlideTransition(direction="left")
        self.manager.current = "wellness"


# ─────────────────────────────────────────────────────────────
#  Screen 2 — Wellness metrics input
# ─────────────────────────────────────────────────────────────

class WellnessScreen(Screen):
    """
    Scrollable form for morning wellness metrics.
    Action lags are NOT shown here — they come from local storage.
    """

    def __init__(self, engine, **kwargs):
        super().__init__(**kwargs)
        self.engine = engine
        self._inputs: list[StyledInput] = []
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical")
        root.add_widget(make_header(
            "📊  Morning Metrics",
            "Enter your biometric readings",
        ))

        scroll = ScrollView()
        body = BoxLayout(
            orientation="vertical",
            padding=[dp(16), dp(12)],
            spacing=dp(10),
            size_hint_y=None,
        )
        body.bind(minimum_height=body.setter("height"))

        if self.engine and self.engine.loaded:
            body.add_widget(make_section_label("🔬  Key Physiological Indicators"))

            for feat_info in self.engine.get_wellness_feature_info():
                wi = StyledInput(
                    label=feat_info["label"],
                    hint=feat_info.get("hint", ""),
                    default=str(feat_info.get("default", "")),
                )
                wi.feature_name = feat_info["feature"]
                self._inputs.append(wi)
                body.add_widget(wi)

            note = Label(
                text="✦ Features ranked by SHAP importance. Action history is auto-loaded.",
                font_size=sp(11), color=TEXT_DIM, italic=True,
                halign="center", size_hint_y=None, height=dp(26),
            )
            note.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))
            body.add_widget(note)
        else:
            err = Label(
                text=f"⚠ Model not loaded\n{self.engine.error_message if self.engine else ''}",
                font_size=sp(13), color=ACCENT_RED,
                halign="center", size_hint_y=None, height=dp(80),
            )
            err.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))
            body.add_widget(err)

        scroll.add_widget(body)
        root.add_widget(scroll)

        btn_row = BoxLayout(size_hint_y=None, height=dp(54))

        back_btn = PrimaryButton("←", color=(0.09, 0.14, 0.22, 1))
        back_btn.size_hint_x = 0.2
        back_btn.bind(on_release=self._go_back)
        btn_row.add_widget(back_btn)

        go_btn = PrimaryButton("GET RECOMMENDATION  →")
        go_btn.size_hint_x = 0.8
        go_btn.bind(on_release=self._on_recommend)
        btn_row.add_widget(go_btn)

        root.add_widget(btn_row)
        self.add_widget(root)

    def _go_back(self, *args):
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = "home"

    def _on_recommend(self, *args):
        if not (self.engine and self.engine.loaded):
            return

        morning_inputs = {}
        for wi in self._inputs:
            try:
                morning_inputs[wi.feature_name] = float(wi.value)
            except ValueError:
                morning_inputs[wi.feature_name] = float("nan")

        try:
            result = self.engine.simulate(morning_inputs)
            rs = self.manager.get_screen("result")
            rs.show_result(result)
            self.manager.transition = SlideTransition(direction="left")
            self.manager.current = "result"
        except Exception as e:
            print(f"Simulation error: {e}")


# ─────────────────────────────────────────────────────────────
#  Screen 3 — Results
# ─────────────────────────────────────────────────────────────

class ResultCard(BoxLayout):
    """Card showing one scenario's predicted next-workout EF delta."""

    def __init__(self, action: str, score: float, interpretation: str,
                 is_recommended: bool = False, **kwargs):
        super().__init__(orientation="vertical", spacing=dp(4),
                         padding=[dp(14), dp(12)], **kwargs)
        self.size_hint_y = None
        self.height = dp(110) if is_recommended else dp(96)

        color = ACTION_PALETTE.get(action, ACCENT_BLUE)
        if is_recommended:
            bg = (color[0]*0.28, color[1]*0.28, color[2]*0.28, 1.0)
        else:
            bg = BG_CARD2

        _bg_canvas(self, bg, radius=dp(10))

        # Border accent on recommended
        if is_recommended:
            with self.canvas.before:
                Color(*color)
                RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
            _bg_canvas(self, (color[0]*0.22, color[1]*0.22, color[2]*0.22, 1),
                       radius=dp(10))

        header = BoxLayout(size_hint_y=None, height=dp(28))
        icon = "⭐ " if is_recommended else "  "
        name_lbl = Label(
            text=f"{icon}{action.upper()}",
            font_size=sp(15 if is_recommended else 13),
            bold=True, color=color, halign="left",
        )
        name_lbl.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))
        header.add_widget(name_lbl)
        if is_recommended:
            badge = Label(
                text="RECOMMENDED", font_size=sp(9),
                bold=True, color=color, halign="right",
            )
            badge.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))
            header.add_widget(badge)
        self.add_widget(header)

        # EF delta displayed as a percentage-style value
        sign = "+" if score >= 0 else ""
        score_lbl = Label(
            text=f"EF outlook: {sign}{score*100:.1f}% vs baseline",
            font_size=sp(11), color=TEXT_MUTED, halign="left",
            size_hint_y=None, height=dp(18),
        )
        score_lbl.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))
        self.add_widget(score_lbl)

        trend_color = (
            ACCENT_GREEN if score > 0.005
            else ACCENT_AMBER if score > -0.005
            else ACCENT_RED
        )
        interp_lbl = Label(
            text=interpretation, font_size=sp(13), bold=True,
            color=trend_color, halign="left",
            size_hint_y=None, height=dp(22),
        )
        interp_lbl.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))
        self.add_widget(interp_lbl)


class ResultScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._root = BoxLayout(orientation="vertical")
        self.add_widget(self._root)

    def show_result(self, result: dict):
        self._root.clear_widgets()

        recommended = result["recommended_action"]
        scores = result.get("scores", result.get("slopes", {}))
        interpretations = result["interpretation"]
        confidence = result.get("confidence", "")
        history_used = result.get("history_used", {})
        readiness = result.get("readiness_score", None)

        self._root.add_widget(make_header(
            f"Today:  {recommended}",
            f"Confidence: {confidence}",
        ))

        scroll = ScrollView()
        body = BoxLayout(
            orientation="vertical",
            padding=[dp(16), dp(12)],
            spacing=dp(10),
            size_hint_y=None,
        )
        body.bind(minimum_height=body.setter("height"))

        # Readiness score gauge
        if readiness is not None:
            r_color = (
                ACCENT_GREEN if readiness >= 65
                else ACCENT_AMBER if readiness >= 40
                else ACCENT_RED
            )
            r_label = (
                "Ready to Train" if readiness >= 65
                else "Moderate Readiness" if readiness >= 40
                else "Recovery Priority"
            )
            readiness_row = BoxLayout(
                size_hint_y=None, height=dp(52),
                spacing=dp(12), padding=[dp(4), dp(4)],
            )
            _bg_canvas(readiness_row, BG_CARD2, radius=dp(8))
            r_num = Label(
                text=f"{readiness}",
                font_size=sp(28), bold=True, color=r_color,
                size_hint_x=0.25, halign="center",
            )
            r_num.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))
            r_desc = BoxLayout(orientation="vertical")
            r_title = Label(
                text="Readiness Score",
                font_size=sp(10), color=TEXT_MUTED, halign="left",
                size_hint_y=None, height=dp(18),
            )
            r_title.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))
            r_sub = Label(
                text=r_label,
                font_size=sp(13), bold=True, color=r_color, halign="left",
                size_hint_y=None, height=dp(22),
            )
            r_sub.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))
            r_desc.add_widget(r_title)
            r_desc.add_widget(r_sub)
            readiness_row.add_widget(r_num)
            readiness_row.add_widget(r_desc)
            body.add_widget(readiness_row)

        # Context line: history used
        ctx_text = (
            f"Context: 2 days ago = {history_used.get('lag_2','?')}  ·  "
            f"3 days ago = {history_used.get('lag_3','?')}"
        )
        ctx_lbl = Label(
            text=ctx_text, font_size=sp(11), color=TEXT_DIM,
            halign="center", size_hint_y=None, height=dp(22),
        )
        ctx_lbl.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))
        body.add_widget(ctx_lbl)

        body.add_widget(make_section_label("📈  Next Workout Efficiency Forecast"))

        # Recommended first, then others
        order = [recommended] + [a for a in ("Rest", "Easy", "Hard") if a != recommended]
        for action in order:
            card = ResultCard(
                action=action,
                score=scores[action],
                interpretation=interpretations[action],
                is_recommended=(action == recommended),
            )
            body.add_widget(card)

        footnote = Label(
            text=(
                "Hybrid model: XGBoost wellness signal (HRV, sleep, CTL)\n"
                "+ Banister fatigue-recovery adjustment for training choice."
            ),
            font_size=sp(10), color=TEXT_DIM, halign="center",
            size_hint_y=None, height=dp(42),
        )
        footnote.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))
        body.add_widget(footnote)

        scroll.add_widget(body)
        self._root.add_widget(scroll)

        back = PrimaryButton("← NEW ASSESSMENT", color=(0.09, 0.14, 0.22, 1))
        back.bind(on_release=self._go_home)
        self._root.add_widget(back)

    def _go_home(self, *args):
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = "home"


# ─────────────────────────────────────────────────────────────
#  Error screen — shown instead of crashing
# ─────────────────────────────────────────────────────────────

class ErrorScreen(Screen):
    """Full-screen error display so crashes are readable on device."""
    def __init__(self, error_text: str, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical")

        hdr = BoxLayout(size_hint_y=None, height=dp(60),
                        padding=[dp(16), dp(10)])
        with hdr.canvas.before:
            Color(0.5, 0.05, 0.05, 1)
            Rectangle(pos=hdr.pos, size=hdr.size)
        hdr.bind(pos=lambda w, v: setattr(hdr.canvas.before.children[1], 'pos', v),
                 size=lambda w, v: setattr(hdr.canvas.before.children[1], 'size', v))
        hdr_lbl = Label(text="STARTUP ERROR", font_size=sp(18), bold=True,
                        color=(1, 0.4, 0.4, 1))
        hdr.add_widget(hdr_lbl)
        root.add_widget(hdr)

        scroll = ScrollView()
        err_lbl = Label(
            text=error_text,
            font_size=sp(11),
            color=(1, 0.8, 0.8, 1),
            halign="left",
            valign="top",
            text_size=(Window.width - dp(32), None),
            size_hint_y=None,
            padding=[dp(12), dp(12)],
        )
        err_lbl.bind(texture_size=lambda i, v: setattr(i, 'height', v[1]))
        scroll.add_widget(err_lbl)
        root.add_widget(scroll)

        self.add_widget(root)


# ─────────────────────────────────────────────────────────────
#  App root
# ─────────────────────────────────────────────────────────────

class CyclingCoachApp(App):
    title = "Cycling Coach"

    def build(self):
        try:
            return self._build_app()
        except Exception:
            tb = traceback.format_exc()
            # Write crash log to a discoverable location
            try:
                import os
                log_paths = [
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'crash.log'),
                    '/sdcard/cycling_coach_crash.log',
                ]
                for lp in log_paths:
                    try:
                        with open(lp, 'w') as f:
                            f.write(tb)
                        break
                    except Exception:
                        pass
            except Exception:
                pass
            sm = ScreenManager()
            sm.add_widget(ErrorScreen(name="error", error_text=tb))
            return sm

    def _build_app(self):
        _log('_build_app() called')
        # Enable faulthandler to log segfaults (native crashes)
        try:
            import faulthandler
            for _fp in _LOG_PATHS:
                try:
                    _fh = open(_fp + '.fault', 'w')
                    faulthandler.enable(file=_fh)
                    _log(f'faulthandler enabled -> {_fp}.fault')
                    break
                except Exception:
                    pass
        except Exception as _fe:
            _log(f'faulthandler setup failed: {_fe}')

        _log('step1: setting Window.clearcolor...')
        Window.clearcolor = BG_DARK
        _log('step2: Window.clearcolor OK')

        self.engine = None
        _log('step3: checking CoachEngine availability...')
        if CoachEngine is not None:
            _log('step4: CoachEngine available, calling constructor...')
            try:
                self.engine = CoachEngine()
                _log('step5: CoachEngine() constructed OK')
                _log('step6: calling engine.load()...')
                ok = self.engine.load()
                _log(f'step7: load() returned {ok} | error={self.engine.error_message!r}')
                if not ok:
                    _log(f'[Engine not loaded] {self.engine.error_message}')
            except Exception as e:
                _log(f'step-FAIL: Engine error: {traceback.format_exc()}')
                self.engine = None
        else:
            _log(f'step4: CoachEngine is None | import error={ENGINE_IMPORT_ERROR}')

        _log('step8: creating ScreenManager...')
        sm = ScreenManager()
        _log('step9: adding HomeScreen...')
        sm.add_widget(HomeScreen(name="home",     engine=self.engine))
        _log('step10: adding WellnessScreen...')
        sm.add_widget(WellnessScreen(name="wellness", engine=self.engine))
        _log('step11: adding ResultScreen...')
        sm.add_widget(ResultScreen(name="result"))
        sm.current = "home"
        _log('step12: _build_app() COMPLETE - returning ScreenManager')
        return sm


if __name__ == "__main__":
    Window.size = (400, 760)
    CyclingCoachApp().run()
