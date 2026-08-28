"""The input engine: timing, humanization, and the click/key loops.

Kept apart from the interface so the behavior can be reasoned about — and
tested — without constructing a window.
"""

import math
import random
import time
import tkinter as tk

from pynput.mouse import Button

from .keys import parse_combo, parse_sequence


class Engine:
    """Click and key loops. Mixed into the app, which supplies the controllers."""


    # ---- numbers -------------------------------------------------------- #
    @staticmethod
    def _num(var, default=0.0):
        try:
            return float(var.get())
        except (ValueError, tk.TclError):
            return default

    def _interval_of(self, val_name, unit_name):
        mult = {"ms": 0.001, "sec": 1.0, "min": 60.0}.get(self.vars[unit_name].get(), 0.001)
        return max(self._num(self.vars[val_name]) * mult, 0.0)


    # ---- config snapshots ------------------------------------------------ #
    def _mouse_cfg(self):
        return dict(
            button={"Left": Button.left, "Right": Button.right,
                    "Middle": Button.middle}[self.vars["mouse_button"].get()],
            action=self.vars["click_action"].get(),
            count=2 if self.vars["click_type"].get() == "Double" else 1,
            base=self._interval_of("click_val", "click_unit"),
            rand=self._num(self.vars["click_rand"]) / 1000.0,
            target_mode=self.vars["target_mode"].get(),
            fixed=(int(self._num(self.vars["fixed_x"])), int(self._num(self.vars["fixed_y"]))),
            points=list(self.points),
            smooth=bool(self.vars["smooth_move"].get()),
            jitter=int(self._num(self.vars["jitter_px"])) if self.vars["jitter_on"].get() else 0,
            hold_on=bool(self.vars["hold_rand_on"].get()),
            hold_min=self._num(self.vars["hold_min"]) / 1000.0,
            hold_max=self._num(self.vars["hold_max"]) / 1000.0,
            burst_on=bool(self.vars["burst_on"].get()),
            burst_n=max(int(self._num(self.vars["burst_n"])), 1),
            burst_pause=self._num(self.vars["burst_pause"]),
            **self._stop_cfg())

    def _key_cfg(self):
        return dict(
            mode=self.vars["key_mode"].get(),
            value=self.vars["key_value"].get(),
            single=self.spam_key,
            base=self._interval_of("key_val_int", "key_unit"),
            rand=self._num(self.vars["key_rand"]) / 1000.0,
            hold_on=bool(self.vars["hold_rand_on"].get()),
            hold_min=self._num(self.vars["hold_min"]) / 1000.0,
            hold_max=self._num(self.vars["hold_max"]) / 1000.0,
            **self._stop_cfg())

    def _scroll_cfg(self):
        step = max(int(self._num(self.vars["scroll_amount"], 1)), 1)
        return dict(
            # pynput scrolls up for positive dy, so "Down" is negative
            dy=step if self.vars["scroll_dir"].get() == "Up" else -step,
            base=self._interval_of("scroll_val", "scroll_unit"),
            rand=self._num(self.vars["scroll_rand"]) / 1000.0,
            **self._stop_cfg())

    def _stop_cfg(self):
        return dict(stop_mode=self.vars["stop_mode"].get(),
                    stop_count=max(int(self._num(self.vars["stop_count"])), 1),
                    stop_time=max(self._num(self.vars["stop_time"]), 0.1))


    # ---- primitives ------------------------------------------------------ #
    def _sleep(self, seconds, check):
        end = time.time() + max(seconds, 0)
        while check() and time.time() < end:
            time.sleep(min(0.02, max(end - time.time(), 0)))

    def _move_to(self, x, y, smooth):
        if not smooth:
            self.mouse_ctl.position = (x, y); return
        sx, sy = self.mouse_ctl.position
        steps = max(int(math.hypot(x - sx, y - sy) / 40), 6)
        for i in range(1, steps + 1):
            t = i / steps
            ease = t * t * (3 - 2 * t)
            self.mouse_ctl.position = (sx + (x - sx) * ease + random.uniform(-1, 1),
                                       sy + (y - sy) * ease + random.uniform(-1, 1))
            time.sleep(0.005)

    def _hold_time(self, cfg):
        if cfg["hold_on"]:
            lo, hi = sorted((cfg["hold_min"], cfg["hold_max"]))
            return random.uniform(lo, hi)
        return 0.008

    def _rand_interval(self, cfg):
        iv = cfg["base"] + (random.uniform(-cfg["rand"], cfg["rand"]) if cfg["rand"] else 0)
        return max(iv, 0.001)

    def _finished_from_thread(self):
        """Ask the interface to wrap up, from a worker thread.

        Tk is not thread-safe, so the loops hand back through `after`. If the
        window is already closing there is no interpreter left to schedule on
        and Tk raises, which would surface as an unhandled thread exception.
        Nothing useful can be done at that point, so it is swallowed.
        """
        try:
            self.root.after(0, self._auto_finished)
        except (RuntimeError, tk.TclError):
            pass

    def _reached_limit(self, cfg, done, start):
        if cfg["stop_mode"] == "Count" and done >= cfg["stop_count"]:
            return True
        if cfg["stop_mode"] == "Time" and (time.time() - start) >= cfg["stop_time"]:
            return True
        return False

    # ---- loops ----------------------------------------------------------- #
    def _click_loop(self, cfg):
        start = time.time(); done = 0; idx = 0; burst = 0
        while self.mouse_active:
            if cfg["target_mode"] == "Fixed":
                tx, ty = cfg["fixed"]; move = True
            elif cfg["target_mode"] == "Multi" and cfg["points"]:
                tx, ty = cfg["points"][idx % len(cfg["points"])]; idx += 1; move = True
            else:
                tx, ty = self.mouse_ctl.position; move = cfg["jitter"] > 0
            if cfg["jitter"]:
                tx += random.randint(-cfg["jitter"], cfg["jitter"])
                ty += random.randint(-cfg["jitter"], cfg["jitter"])
            if move:
                self._move_to(tx, ty, cfg["smooth"])
            hold = self._hold_time(cfg)
            for c in range(cfg["count"]):
                self.mouse_ctl.press(cfg["button"]); time.sleep(hold)
                self.mouse_ctl.release(cfg["button"])
                if c < cfg["count"] - 1:
                    time.sleep(0.03)
            done += 1; self.run_clicks += 1; self.total_clicks += 1
            if self._reached_limit(cfg, done, start):
                self._finished_from_thread(); break
            if cfg["burst_on"]:
                burst += 1
                if burst >= cfg["burst_n"]:
                    burst = 0
                    self._sleep(cfg["burst_pause"], lambda: self.mouse_active)
                    continue
            self._sleep(self._rand_interval(cfg), lambda: self.mouse_active)

    def _key_loop(self, cfg):
        start = time.time(); done = 0
        seq = parse_sequence(cfg["value"]) if cfg["mode"] == "Sequence" else None
        combo = parse_combo(cfg["value"]) if cfg["mode"] == "Combo" else None
        while self.key_active:
            try:
                if cfg["mode"] == "Text":
                    if cfg["value"]:
                        self.kbd_ctl.type(cfg["value"])
                elif cfg["mode"] == "Sequence":
                    for k in (seq or []):
                        self._tap(k, cfg); time.sleep(0.01)
                elif cfg["mode"] == "Combo":
                    for k in (combo or []):
                        self.kbd_ctl.press(k); time.sleep(0.005)
                    for k in reversed(combo or []):
                        self.kbd_ctl.release(k)
                else:
                    self._tap(cfg["single"], cfg)
            except Exception:
                pass
            done += 1; self.run_clicks += 1; self.total_clicks += 1
            if self._reached_limit(cfg, done, start):
                self._finished_from_thread(); break
            self._sleep(self._rand_interval(cfg), lambda: self.key_active)

    def _hold_mouse(self, cfg):
        """Press the button and keep it down until stopped.

        The release sits in a `finally` so it happens even if the thread is
        torn down or something raises. A button left physically pressed is the
        worst failure this app could have: it would keep dragging across the
        user's desktop with no obvious way to stop it.
        """
        pressed = False
        try:
            self.mouse_ctl.press(cfg["button"])
            pressed = True
            self.run_clicks += 1
            self.total_clicks += 1
            while self.mouse_active:
                time.sleep(0.02)
        finally:
            if pressed:
                try:
                    self.mouse_ctl.release(cfg["button"])
                except Exception:
                    pass

    def _hold_key(self, cfg):
        """Hold one key down until stopped. Released in a `finally`, as above."""
        key = cfg["single"]
        pressed = False
        try:
            self.kbd_ctl.press(key)
            pressed = True
            self.run_clicks += 1
            self.total_clicks += 1
            while self.key_active:
                time.sleep(0.02)
        finally:
            if pressed:
                try:
                    self.kbd_ctl.release(key)
                except Exception:
                    pass

    def _scroll_loop(self, cfg):
        start = time.time()
        done = 0
        while self.scroll_active:
            try:
                self.mouse_ctl.scroll(0, cfg["dy"])
            except Exception:
                pass
            done += 1
            self.run_clicks += 1
            self.total_clicks += 1
            if self._reached_limit(cfg, done, start):
                self._finished_from_thread()
                break
            self._sleep(self._rand_interval(cfg), lambda: self.scroll_active)

    def _tap(self, key, cfg):
        self.kbd_ctl.press(key); time.sleep(self._hold_time(cfg)); self.kbd_ctl.release(key)

    def _auto_finished(self):
        if self.mouse_active or self.key_active:
            self.stop_all()
            self.status_text.set("Finished")
            self.root.after(2000, self._refresh_running_ui)
