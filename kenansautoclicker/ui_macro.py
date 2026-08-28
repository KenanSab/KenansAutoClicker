"""Recording and playing macros: the controls, the countdown, the safeguards."""

import threading
import tkinter as tk
from tkinter import filedialog, messagebox

from .recorder import Player, Recorder, load_macro, save_macro, summarize


class MacroControls:
    """Record/playback behavior, mixed into the application window."""

    # ---- recording ------------------------------------------------------- #
    def _toggle_recording(self):
        if self.recorder is not None and self.recorder.recording:
            self._stop_recording()
        else:
            self._begin_countdown(3)

    def _begin_countdown(self, n):
        """Count down before recording starts.

        Without this the click on the Record button would be the first thing
        recorded, and every playback would begin by clicking that button again.
        """
        if self.macro_countdown_id is not None:
            self.root.after_cancel(self.macro_countdown_id)
            self.macro_countdown_id = None
        if n <= 0:
            self._start_recording()
            return
        self.macro_rec_btn.configure(text=f"Starting in {n}")
        self.status_text.set(f"Recording starts in {n}…")
        self.macro_countdown_id = self.root.after(
            1000, lambda: self._begin_countdown(n - 1))

    def _start_recording(self):
        # never record the hotkeys, or stopping would replay as a keystroke
        ignore = {self.master_hotkey, self.panic_hotkey,
                  self.mouse_hotkey, self.key_hotkey}
        self.recorder = Recorder(capture_moves=bool(self.vars["macro_moves"].get()),
                                 ignore_keys=ignore)
        self.recorder.start()
        self.macro_rec_btn.configure(text="Stop recording")
        self.status_text.set(f"Recording. Press {self._hotkey_label()} to stop.")
        self._refresh_macro_label()

    def _stop_recording(self):
        if self.recorder is None:
            return
        self.macro_events = self.recorder.stop()
        self.recorder = None
        self.macro_rec_btn.configure(text="Record")
        self._refresh_macro_label()
        self.status_text.set(f"Recorded {summarize(self.macro_events)}")
        self.root.after(2500, self._refresh_running_ui)
        if self.macro_events:
            self.vars["macro_enabled"].set(True)

    def _hotkey_label(self):
        from .keys import key_to_label
        return key_to_label(self.master_hotkey)

    def _refresh_macro_label(self):
        if not hasattr(self, "macro_lbl"):
            return
        if self.recorder is not None and self.recorder.recording:
            self.macro_lbl.configure(text=f"recording… {len(self.recorder.events)} events")
            self.root.after(400, self._refresh_macro_label)
        else:
            self.macro_lbl.configure(text=summarize(self.macro_events))

    # ---- playback -------------------------------------------------------- #
    def _macro_loop(self):
        """Replay the recording on a worker thread."""
        player = Player(self.mouse_ctl, self.kbd_ctl)
        try:
            repeat = int(self._num(self.vars["macro_repeat"], 1))
        except (TypeError, ValueError):
            repeat = 1
        speed = self._num(self.vars["macro_speed"], 1.0) or 1.0

        def keep_going():
            return self.macro_active

        def counted():
            self.run_clicks += 1
            self.total_clicks += 1

        events = list(self.macro_events)
        player.play(events, keep_going, speed=speed, repeat=repeat,
                    on_finished=self._finished_from_thread)
        self.macro_active = False

    # ---- files ----------------------------------------------------------- #
    def _save_macro(self):
        if not self.macro_events:
            messagebox.showinfo("Macro", "Record something first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("Macro", "*.json")],
            initialfile="my_macro.json")
        if not path:
            return
        try:
            save_macro(path, self.macro_events)
            self.status_text.set("Macro saved")
            self.root.after(1600, self._refresh_running_ui)
        except OSError as exc:
            messagebox.showerror("Macro", f"Could not save:\n{exc}")

    def _load_macro(self):
        path = filedialog.askopenfilename(filetypes=[("Macro", "*.json")])
        if not path:
            return
        try:
            events = load_macro(path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Macro", f"Could not read that file:\n{exc}")
            return
        if not events:
            messagebox.showerror("Macro", "That file has no usable events in it.")
            return
        self.macro_events = events
        self.vars["macro_enabled"].set(True)
        self._refresh_macro_label()
        self.status_text.set(f"Loaded {summarize(events)}")
        self.root.after(2000, self._refresh_running_ui)
