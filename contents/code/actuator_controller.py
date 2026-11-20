# This Python file uses the following encoding: utf-8
"""Actuator definitions, valve state tracking, and safety interlocks (`actuator_controller.py`)."""

import json

from PySide6 import QtCore


class ActuatorController(QtCore.QObject):
    """Manages SAFE/ARMED interlocks, valve states, and actuator commands."""

    config_changed = QtCore.Signal()
    armed_changed = QtCore.Signal(bool)
    valves_changed = QtCore.Signal()
    valve_state_updated = QtCore.Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._armed = False
        self._valve_definitions: list[dict] = []
        self._valves: dict[str, str] = {}

    @staticmethod
    def normalize_valve_state(state: str) -> str:
        s = str(state).strip().upper()
        aliases = {
            "CLOSE": "CLOSED",
            "TRANSIT": "ACTUATING",
            "FILLING": "FILL",
            "VENTING": "VENT",
        }
        return aliases.get(s, s)

    @property
    def armed(self) -> bool:
        return self._armed

    @armed.setter
    def armed(self, value: bool) -> None:
        val = bool(value)
        if self._armed != val:
            self._armed = val
            self.armed_changed.emit(val)

    @property
    def valve_definitions(self) -> list[dict]:
        return list(self._valve_definitions)

    @property
    def valves(self) -> dict[str, str]:
        return dict(self._valves)

    def seed_valves_from_config(self, config_data: dict) -> None:
        defs = config_data.get("actuators") or config_data.get("valves")
        if isinstance(defs, list) and defs:
            self.apply_actuator_definitions(defs)

    def apply_actuator_definitions(self, definitions: list) -> None:
        valid_defs = [
            dict(item)
            for item in definitions
            if isinstance(item, dict) and item.get("id")
        ]
        self._valve_definitions = valid_defs
        seeded = {}
        for item in valid_defs:
            vid = item["id"]
            default_st = self.normalize_valve_state(item.get("normal_state", "CLOSED"))
            seeded[vid] = self._valves.get(vid, default_st)
        self._valves = seeded
        self.config_changed.emit()
        self.valves_changed.emit()

    def get_valve_def(self, valve_id: str) -> dict:
        for item in self._valve_definitions:
            if item.get("id") == valve_id:
                return item
        return {}

    def apply_valve_state(self, valve_id: str, state: str) -> None:
        norm = self.normalize_valve_state(state)
        if not valve_id or not norm:
            return
        if self._valves.get(valve_id) != norm:
            self._valves[valve_id] = norm
            self.valve_state_updated.emit(valve_id, norm)
            self.valves_changed.emit()

    def apply_valves_map(self, valves_map: dict) -> None:
        for vid, st in valves_map.items():
            self._valves[vid] = self.normalize_valve_state(st)
        self.valves_changed.emit()

    def actuate_valve(
        self, valve_id: str, action: str, send_ws_fn, log_warn_fn
    ) -> bool:
        """Validates armed/interlock state and sends an outbound CTRL packet."""
        if not self._armed:
            log_warn_fn(f"Cannot actuate {valve_id}: system is SAFE (disarmed).")
            return False

        vdef = self.get_valve_def(valve_id)
        if vdef.get("external", False):
            log_warn_fn(f"{valve_id} is externally controlled.")
            return False

        current = self._valves.get(valve_id, "")
        if vdef.get("single_use", False) and current in ("FIRED", "DISCONNECTED"):
            log_warn_fn(f"{valve_id} is single-use and already {current}.")
            return False

        act = str(action).strip().upper()
        payload = {
            "type": "command",
            "command": "CTRL",
            "valve": valve_id,
            "action": act,
        }
        send_ws_fn(json.dumps(payload))
        return True

    def abort(self, send_ws_fn, log_warn_fn) -> None:
        """Sends emergency abort command regardless of armed state."""
        payload = {"type": "abort", "command": "ABORT"}
        send_ws_fn(json.dumps(payload))
        log_warn_fn("EMERGENCY ABORT command sent.")
