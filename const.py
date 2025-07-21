from pathlib import Path
import yaml

CONF = yaml.safe_load(Path("config.yaml").read_text())
SECRETS = yaml.safe_load(Path("secrets.yaml").read_text())
TOKEN = SECRETS["homeassistant"]["token"]
BASE_URL = SECRETS["homeassistant"]["url"].rstrip("/")
REST_URL = f"{BASE_URL}/api"
WS_URL = (
    BASE_URL.replace("http://", "ws://").replace("https://", "wss://")
    + "/api/websocket"
)
CONF_ENTITIES = CONF["entities"]
TIMEZONE = CONF["locale"].get("timezone", "America/Los_Angeles")
WATCHED = CONF_ENTITIES.keys()
SUNSETHUE_API_KEY = SECRETS["sunsethue"]["api_key"]
SUNSETHUE_LATITUDE = SECRETS["sunsethue"]["latitude"]
SUNSETHUE_LONGITUDE = SECRETS["sunsethue"]["longitude"]
