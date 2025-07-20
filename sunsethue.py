import requests
import json
from datetime import datetime
import pytz
from const import *


def get_weather_forecast():
    base_url = "https://api.sunsethue.com/event"

    params = {
        "key": SUNSETHUE_API_KEY,
        "latitude": SUNSETHUE_LATITUDE,
        "longitude": SUNSETHUE_LONGITUDE,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "type": "sunset",
    }

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        try:
            print(f"API Error Details: {response.json()}")
        except json.JSONDecodeError:
            print("Could not parse error response from API.")
    except requests.exceptions.RequestException as req_err:
        print(f"An error occurred with the request: {req_err}")
    except Exception as err:
        print(f"An unexpected error occurred: {err}")

    return None


def format_forecast_data(data):
    if not data:
        return "No data available."

    # Check if 'data' key exists
    if "data" not in data:
        return "Invalid data format."

    forecast_data = data["data"]

    # Extract the requested information
    quality = forecast_data.get("quality")
    quality_text = forecast_data.get("quality_text")
    cloud_cover = forecast_data.get("cloud_cover")

    # Golden hour is a list with start and end times
    golden_hour = forecast_data.get("magics", {}).get("golden_hour", [])
    blue_hour = forecast_data.get("magics", {}).get("blue_hour", [])

    # Helper function to format hour data
    def format_hour_time(hour_data, timezone_name="America/Los_Angeles"):
        """Format an hour range time from UTC to specified timezone."""
        if not hour_data or len(hour_data) < 1:
            return "Not available"

        try:
            # Parse the ISO format datetime
            hour_start_utc = datetime.fromisoformat(hour_data[0].replace("Z", "+00:00"))

            # Convert to specified timezone
            local_timezone = pytz.timezone(timezone_name)
            hour_start_local = hour_start_utc.astimezone(local_timezone)

            # Format the time
            return hour_start_local.strftime("%I:%M %p")
        except Exception as e:
            return f"Error processing time: {str(e)}"

    # Format both golden and blue hour times
    golden_hour_str = format_hour_time(golden_hour)
    blue_hour_str = format_hour_time(blue_hour)

    # Format the output as a dictionary
    formatted_data = {
        "quality": quality if quality is not None else None,
        "quality_text": quality_text if quality_text else None,
        "cloud_cover": cloud_cover if cloud_cover is not None else None,
        "golden_hour": golden_hour_str,
        "blue_hour": blue_hour_str,
    }

    return formatted_data
