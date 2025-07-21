from datetime import datetime, timedelta, timezone
import json, requests
import numpy as np, pandas as pd
from homeassistant_api import Client, WebsocketClient
from const import *
from zoneinfo import ZoneInfo


class Entity:
    def __init__(self, entity_id: str, name: str = None):
        self.entity_id = entity_id
        self.params = CONF_ENTITIES.get(entity_id, {})
        self.name = self.params.get("name", name or entity_id)
        self.state_abnormal_str = self.params.get("state_abnormal_str", ["unavailable"])
        if isinstance(self.state_abnormal_str, str):
            self.state_abnormal_str = [self.state_abnormal_str]
        self.state_str_name_mapping = self.params.get("state_str_name_mapping", {})
        # Initialize state and state dictionary
        self._state = None
        self.dict_states = {}

    @property
    def state(self) -> str:
        self._state = self.dict_states.get("state", self._state)
        return self._state

    @property
    def normal(self) -> bool:
        if self.state_abnormal_str and self.state in self.state_abnormal_str:
            return False
        return True

    @property
    def state_name(self) -> str:
        """Get the name of the current state."""
        if self.state in self.state_str_name_mapping:
            return self.state_str_name_mapping[self.state]
        return self.state


ha_states: dict[str, Entity] = {}

for eid in WATCHED:
    ha_states[eid] = Entity(eid)


def attr_diffs(old: dict | None, new: dict) -> dict:
    """Return only keys whose value actually changed."""
    if not old:
        return new
    return {k: new[k] for k, v in new.items() if v != old.get(k)}


def get_entity_state_rest(client, entity_id: str) -> dict | None:
    global ha_states
    try:
        entity = client.get_entity(entity_id=entity_id)
        dict_states = entity.get_state()
        # print(dict_states)
        if dict_states:
            ha_states[entity_id].dict_states = dict_states.model_dump(exclude_none=True)
            state = dict_states.state
            print(f"[{datetime.now():%H:%M:%S}] {entity_id}: {state}")
            return str(state)
        else:
            return None
    except Exception as exc:
        print(f"[!] Couldn't get state for {entity_id}: {exc}")
        return None


def get_entity_state_local(entity_id: str) -> dict | None:
    """Get the current state of an entity from local cache."""
    global ha_states
    if entity_id in ha_states:
        return ha_states[entity_id].state
    else:
        print(f"[!] Entity {entity_id} not found in local cache.")
        return None


def update_entity_from_state_changed(data: dict) -> None:
    """Update the entity state from a state_changed event."""
    global ha_states
    eid = data["entity_id"]
    new_state = data["new_state"]
    old_state = ha_states.get(eid).dict_states

    state_changed = False

    # 1) state string changed? (on/off/unavailable/…)
    if not old_state or old_state["state"] != new_state["state"]:
        state_changed = True
        print(
            f"[{datetime.now():%H:%M:%S}] {eid}: "
            f"{old_state and old_state['state']} → {new_state['state']}"
        )

    # 2) attribute diffs
    diff = attr_diffs(
        old_state and old_state.get("attributes"), new_state["attributes"]
    )
    if diff:
        pretty = ", ".join(f"{k}: {v}" for k, v in diff.items())
        print(f"    ↳ attrs changed → {pretty}")

    ha_states[eid].dict_states = new_state  # update cache

    return state_changed


def get_sensor_history(eid: str) -> pd.DataFrame | None:
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }

    # Get timezone object based on the configured timezone
    tz = ZoneInfo(TIMEZONE)

    # Get start and end times in the configured timezone
    start = (datetime.now(tz) - timedelta(hours=24)).isoformat()
    end = datetime.now(tz).isoformat()

    url = f"{BASE_URL}/api/history/period/{start}"

    params = {
        "filter_entity_id": eid,
        "end_time": end,
        "minimal_response": "true",
        "significant_changes_only": "false",
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        # print(f"History for {eid} from {start} to {end}:")

        times = []
        temps = []

        if data and len(data) > 0:
            hist = data[0]
            # print(f"Found {len(hist)} history entries:")

            for entry in hist:
                last_changed = entry.get("last_changed")
                state = entry.get("state")
                try:
                    temp = float(state)
                except (TypeError, ValueError):
                    temp = np.nan
                times.append(last_changed)
                temps.append(temp)

            # Create pandas DataFrame with timezone-aware timestamps
            df = pd.DataFrame(
                {"time": pd.to_datetime(times, utc=True), "temperature": temps}
            )
            # Convert to the configured timezone
            df["time"] = df["time"].dt.tz_convert(TIMEZONE)
            # print(df)

            # If you want a numpy matrix:
            # matrix = df[["time", "temperature"]].to_numpy()
            # print(matrix)
        else:
            print("[!] get_sensor_history: No history data found")
            df = pd.DataFrame({"time": [], "temperature": []})

        return df

    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    return None


with Client(REST_URL, TOKEN) as client:
    for eid in WATCHED:
        get_entity_state_rest(client, eid)

if __name__ == "__main__":
    get_sensor_history("sensor.temperature_humidity_sensor_a63c_temperature")
