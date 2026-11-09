
import os
import json
import urllib.request
import urllib.parse
import urllib.error

from datetime import date
from dotenv import load_dotenv

from strands import Agent, tool
from strands.models.openai import OpenAIModel


# --------------------------------------------------
# Environment configuration
# --------------------------------------------------

load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")

if not groq_api_key:
    raise ValueError(
        "GROQ_API_KEY not found. Check your .env file."
    )


# --------------------------------------------------
# Common API helper
# --------------------------------------------------

def fetch_api_data(base_url: str, params: dict) -> dict:
    """Fetch JSON data from an external API."""

    query_string = urllib.parse.urlencode(params)
    url = f"{base_url}?{query_string}"

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "TravelAssistantAgent/1.0"
        }
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"API returned HTTP error {error.code}: {error.reason}"
        )

    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Could not connect to API: {error.reason}"
        )

    except json.JSONDecodeError:
        raise RuntimeError("API returned invalid JSON data.")


def resolve_city_coordinates(city: str) -> dict:
    """Resolve a city using its name, region and country."""

    parts = [part.strip() for part in city.split(",") if part.strip()]

    search_name = parts[0]

    requested_region = parts[1] if len(parts) >= 3 else None
    requested_country = parts[-1] if len(parts) >= 2 else None

    location_data = fetch_api_data(
        "https://geocoding-api.open-meteo.com/v1/search",
        {
            "name": search_name,
            "count": 10,
            "language": "en",
            "format": "json"
        }
    )

    locations = location_data.get("results", [])

    exact_matches = [
        item for item in locations
        if item.get("name", "").casefold() == search_name.casefold()
    ]

    if not exact_matches:
        raise ValueError(
            f"No matching location found for {city}."
        )

    candidates = exact_matches

    if requested_country:
        country_matches = [
            item for item in candidates
            if item.get("country", "").casefold()
            == requested_country.casefold()
        ]

        if country_matches:
            candidates = country_matches

    if requested_region:
        region_matches = [
            item for item in candidates
            if item.get("admin1", "").casefold()
            == requested_region.casefold()
        ]

        if region_matches:
            candidates = region_matches

    if len(candidates) != 1:
        details = [
            {
                "name": item.get("name"),
                "region": item.get("admin1"),
                "country": item.get("country")
            }
            for item in candidates
        ]

        raise ValueError(
            f"Ambiguous location for {city}. "
            f"Matching locations: {details}"
        )

    location = candidates[0]

    return {
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "name": location.get("name", search_name),
        "region": location.get("admin1", ""),
        "country": location.get("country", "")
    }

# --------------------------------------------------
# Weather description helper
# --------------------------------------------------

def describe_weather_code(code: int) -> str:

    weather_codes = {
        0: "clear sky",
        1: "mainly clear",
        2: "partly cloudy",
        3: "overcast",
        45: "fog",
        48: "depositing rime fog",
        51: "light drizzle",
        53: "moderate drizzle",
        55: "dense drizzle",
        56: "freezing drizzle",
        57: "dense freezing drizzle",
        61: "slight rain",
        63: "moderate rain",
        65: "heavy rain",
        66: "freezing rain",
        67: "heavy freezing rain",
        71: "slight snowfall",
        73: "moderate snowfall",
        75: "heavy snowfall",
        77: "snow grains",
        80: "slight rain showers",
        81: "moderate rain showers",
        82: "violent rain showers",
        85: "slight snow showers",
        86: "heavy snow showers",
        95: "thunderstorm",
        96: "thunderstorm with slight hail",
        99: "thunderstorm with heavy hail"
    }

    return weather_codes.get(code, "unknown conditions")


# --------------------------------------------------
# Tool 1: Live weather forecast
# --------------------------------------------------

@tool
def get_weather_forecast(city: str, days: int) -> dict:
    """Get a live weather forecast for a destination."""

    print("TOOL CALLED: get_weather_forecast")

    if not 1 <= days <= 16:
        raise ValueError("Forecast days must be between 1 and 16.")

    search_name = city.split(",", 1)[0].strip()

    # Goa is resolved using Panaji's coordinates.
    if (
        search_name.casefold() in {"goa", "panaji"}
        or "panaji" in search_name.casefold()
    ):
        latitude = 15.4909
        longitude = 73.8278
        location_name = "Panaji"
        region = "Goa"
        country = "India"

    else:
        location_data = fetch_api_data(
            "https://geocoding-api.open-meteo.com/v1/search",
            {
                "name": search_name,
                "count": 10,
                "language": "en",
                "format": "json"
            }
        )

        locations = location_data.get("results", [])

        if not locations:
            raise ValueError(
                f"Could not find the location: {city}"
            )

        exact_matches = [
            item for item in locations
            if item.get("name", "").casefold()
            == search_name.casefold()
        ]

        location = (
            exact_matches[0]
            if exact_matches
            else locations[0]
        )

        latitude = location["latitude"]
        longitude = location["longitude"]
        location_name = location.get("name", search_name)
        region = location.get("admin1", "")
        country = location.get("country", "")

    forecast_data = fetch_api_data(
        "https://api.open-meteo.com/v1/forecast",
        {
            "latitude": latitude,
            "longitude": longitude,
            "daily": (
                "weather_code,"
                "temperature_2m_max,"
                "temperature_2m_min,"
                "precipitation_probability_max"
            ),
            "timezone": "auto",
            "forecast_days": days
        }
    )

    daily = forecast_data.get("daily", {})

    if not daily.get("time"):
        raise RuntimeError("Weather forecast data is unavailable.")

    daily_forecast = []

    for index, forecast_date in enumerate(daily["time"]):

        weather_code = daily["weather_code"][index]

        daily_forecast.append({
            "date": forecast_date,
            "high_c": daily["temperature_2m_max"][index],
            "low_c": daily["temperature_2m_min"][index],
            "conditions": describe_weather_code(weather_code),
            "rain_probability_percent": (
                daily["precipitation_probability_max"][index]
            )
        })

    return {
        "source": "Open-Meteo live weather API",
        "city": city,
        "weather_reference": location_name,
        "state_or_region": region,
        "country": country,
        "days": len(daily_forecast),
        "high_c": max(item["high_c"] for item in daily_forecast),
        "low_c": min(item["low_c"] for item in daily_forecast),
        "conditions": daily_forecast[0]["conditions"],
        "daily_forecast": daily_forecast
    }


# --------------------------------------------------
# Tool 2: Weather-based packing suggestions
# --------------------------------------------------

@tool
def suggest_packing_list(
    high_c: float,
    low_c: float,
    days: int,
    conditions: str
) -> dict:
    """Suggest items to pack based on destination weather."""

    print("TOOL CALLED: suggest_packing_list")

    if days < 1:
        raise ValueError("Trip duration must be at least one day.")

    packing_list = []

    if high_c >= 30:
        packing_list.extend([
            "Lightweight cotton clothes",
            "Sunglasses",
            "Sunscreen",
            "Cap or hat",
            "Comfortable footwear"
        ])

    elif low_c <= 10:
        packing_list.extend([
            "Warm jackets",
            "Sweaters",
            "Thermal clothing",
            "Warm socks",
            "Closed shoes"
        ])

    elif low_c <= 18:
        packing_list.extend([
            "Light jacket",
            "Full-sleeve clothes",
            "Comfortable trousers"
        ])

    else:
        packing_list.extend([
            "Comfortable everyday clothes",
            "Walking shoes"
        ])

    weather = conditions.casefold()

    if any(word in weather for word in ["rain", "drizzle", "thunderstorm"]):
        packing_list.extend([
            "Umbrella",
            "Raincoat",
            "Waterproof bag"
        ])

    if any(word in weather for word in ["snow", "freezing"]):
        packing_list.extend([
            "Gloves",
            "Warm socks",
            "Waterproof footwear"
        ])

    packing_list.extend([
        "Personal toiletries",
        "Phone charger",
        "Power bank",
        "Identity documents",
        "Basic medicines"
    ])

    return {
        "trip_duration_days": days,
        "weather_conditions": conditions,
        "temperature_range": f"{low_c}°C to {high_c}°C",
        "packing_list": list(dict.fromkeys(packing_list))
    }


# --------------------------------------------------
# Tool 3: Trip cost estimation
# --------------------------------------------------

@tool
def estimate_trip_cost(
    city: str,
    days: int,
    travellers: int = 1
) -> dict:
    """Estimate accommodation, food and local travel costs in INR."""

    print("TOOL CALLED: estimate_trip_cost")

    if days < 1:
        raise ValueError("Trip duration must be at least one day.")

    if travellers < 1:
        raise ValueError("There must be at least one traveller.")

    city_name = city.split(",")[0].strip().casefold()

    per_night = {
        "goa": 3500,
        "bangalore": 3000,
        "jaipur": 2500,
        "manali": 2800
    }

    accommodation_per_night = per_night.get(city_name, 3000)

    stay = accommodation_per_night * days
    food = 1200 * days * travellers
    local_travel = 800 * days

    total = stay + food + local_travel

    return {
        "destination": city,
        "duration_days": days,
        "travellers": travellers,
        "currency": "INR",
        "estimated_cost": {
            "accommodation": stay,
            "food": food,
            "local_transport": local_travel,
            "total": total
        },
        "cost_per_traveller": round(total / travellers),
        "note": (
            "Approximate planning estimate. "
            "Actual costs depend on accommodation, "
            "food choices and travel preferences."
        )
    }


# --------------------------------------------------
# Tool 4: Destination recommendations
# --------------------------------------------------




@tool
def recommend_places(city: str) -> dict:
    """Find relevant tourist attractions and sightseeing places."""

    print("TOOL CALLED: recommend_places")

    location = resolve_city_coordinates(city)

    latitude = location["latitude"]
    longitude = location["longitude"]
    location_name = location["name"]

    query = f"""
[out:json][timeout:25];
(
  node["tourism"~"attraction|museum|viewpoint|zoo|theme_park"]
  (around:10000,{latitude},{longitude});

  way["tourism"~"attraction|museum|viewpoint|zoo|theme_park"]
  (around:10000,{latitude},{longitude});

  node["historic"~"castle|fort|monument|memorial"]
  (around:10000,{latitude},{longitude});

  way["historic"~"castle|fort|monument|memorial"]
  (around:10000,{latitude},{longitude});
);
out center tags 25;
"""

    endpoints = [
        "https://overpass.private.coffee/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
        "https://overpass-api.de/api/interpreter"
    ]

    places_data = None
    errors = []

    for endpoint in endpoints:
        try:
            request_data = urllib.parse.urlencode({
                "data": query
            }).encode("utf-8")

            request = urllib.request.Request(
                endpoint,
                data=request_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "TravelAssistantAgent/1.0"
                },
                method="POST"
            )

            with urllib.request.urlopen(request, timeout=60) as response:
                places_data = json.loads(
                    response.read().decode("utf-8")
                )

            break

        except Exception as error:
            errors.append(f"{endpoint}: {error}")

    if places_data is None:
        raise RuntimeError(
            "All OpenStreetMap servers failed: "
            + " | ".join(errors)
        )

    places = []

    excluded_words = [
        "home", "residence", "residential",
        "apartment", "private house"
    ]

    for item in places_data.get("elements", []):

        tags = item.get("tags", {})
        name = tags.get("name")

        if not name:
            continue

        if any(word in name.casefold() for word in excluded_words):
            continue

        tourism = tags.get("tourism")
        historic = tags.get("historic")
        natural = tags.get("natural")
        leisure = tags.get("leisure")

        if natural == "beach":
            category = "beach"
        elif historic:
            category = historic
        elif tourism:
            category = tourism
        elif leisure == "park":
            category = "park"
        else:
            continue

        latitude_value = (
            item.get("lat")
            or item.get("center", {}).get("lat")
        )

        longitude_value = (
            item.get("lon")
            or item.get("center", {}).get("lon")
        )

        places.append({
            "name": name,
            "category": category,
            "latitude": latitude_value,
            "longitude": longitude_value
        })

    unique_places = {}

    for place in places:
        unique_places.setdefault(
            place["name"].casefold(),
            place
        )

    results = list(unique_places.values())[:15]

    if not results:
        raise RuntimeError(
            f"No suitable tourist attractions found near {location_name}."
        )

    return {
        "source": "OpenStreetMap",
        "destination": location_name,
        "total_places": len(results),
        "places": results
    }


# --------------------------------------------------
# Tool 5: Hotel and restaurant recommendations
# --------------------------------------------------


@tool
def recommend_hotels_and_restaurants(city: str) -> dict:
    """Find hotels and restaurants near a travel destination."""

    print("TOOL CALLED: recommend_hotels_and_restaurants")

    location = resolve_city_coordinates(city)

    latitude = location["latitude"]
    longitude = location["longitude"]
    location_name = location["name"]

    query = f"""
[out:json][timeout:25];
(
  node["tourism"~"hotel|hostel|guest_house"]
  (around:10000,{latitude},{longitude});

  way["tourism"~"hotel|hostel|guest_house"]
  (around:10000,{latitude},{longitude});

  node["amenity"~"restaurant|cafe"]
  (around:10000,{latitude},{longitude});

  way["amenity"~"restaurant|cafe"]
  (around:10000,{latitude},{longitude});
);
out center tags 30;
"""

    endpoints = [
        "https://overpass.private.coffee/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
        "https://overpass-api.de/api/interpreter"
    ]

    places_data = None
    errors = []

    for endpoint in endpoints:
        try:
            request_data = urllib.parse.urlencode({
                "data": query
            }).encode("utf-8")

            request = urllib.request.Request(
                endpoint,
                data=request_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "TravelAssistantAgent/1.0"
                },
                method="POST"
            )

            with urllib.request.urlopen(request, timeout=60) as response:
                places_data = json.loads(
                    response.read().decode("utf-8")
                )

            break

        except Exception as error:
            errors.append(f"{endpoint}: {error}")

    if places_data is None:
        raise RuntimeError(
            "All OpenStreetMap servers failed: "
            + " | ".join(errors)
        )

    hotels = []
    restaurants = []

    for item in places_data.get("elements", []):
        tags = item.get("tags", {})
        name = tags.get("name")

        if not name:
            continue

        place = {
            "name": name,
            "latitude": (
                item.get("lat")
                or item.get("center", {}).get("lat")
            ),
            "longitude": (
                item.get("lon")
                or item.get("center", {}).get("lon")
            )
        }

        if tags.get("tourism") in {
            "hotel", "hostel", "guest_house"
        }:
            place["type"] = tags["tourism"]
            hotels.append(place)

        elif tags.get("amenity") in {
            "restaurant", "cafe"
        }:
            place["type"] = tags["amenity"]
            restaurants.append(place)

    hotels = list({
        item["name"].casefold(): item
        for item in hotels
    }.values())

    restaurants = list({
        item["name"].casefold(): item
        for item in restaurants
    }.values())

    return {
        "source": "OpenStreetMap",
        "destination": location_name,
        "hotels": hotels[:10],
        "restaurants": restaurants[:10],
        "total_hotels": len(hotels[:10]),
        "total_restaurants": len(restaurants[:10])
    }



# --------------------------------------------------
# Groq model configuration
# --------------------------------------------------

model = OpenAIModel(
    client_args={
        "api_key": groq_api_key,
        "base_url": "https://api.groq.com/openai/v1"
    },
   model_id="openai/gpt-oss-120b",
    params={
        "temperature": 0.3,
        "max_tokens": 4096
    }
)


# --------------------------------------------------
# Travel assistant agent
# --------------------------------------------------

system_prompt = """
You are an intelligent AI Travel Assistant.

Help users plan practical trips using the available tools.

IMPORTANT INSTRUCTIONS:

1. Understand the user's destination, trip duration and number
   of travellers.

2. Always count the user as one traveller.
   For example, "me and 2 friends" means 3 travellers.

3. When weather information is requested, call
   get_weather_forecast to retrieve live weather.

4. When the user asks what to pack, use the actual weather
   information and call suggest_packing_list.

5. When the user asks for tourist attractions or places to visit,
   call recommend_places.

6. Recommend only places returned by recommend_places.
   Do not invent attractions, ratings or opening hours.

7. When the user asks for a trip budget, call estimate_trip_cost.
   Pass the correct total number of travellers.

8. Clearly explain that cost estimates are approximate.

9. Never invent live weather, API results or tool outputs.

10. Present information in a clear, organised and useful format.

11. For a complete travel plan, combine relevant information
    such as weather, attractions, packing and estimated budget.

12. If essential information is missing, ask the user for it.

13. Never assume or invent opening hours, ticket prices,
    ratings or travel times. If the tools do not provide
    this information, clearly say it is not verified.

14. When recommending places, prioritise actual tourist
    attractions over shops, restaurants and unrelated businesses.

    15. When the user provides a trip duration, organise the
    recommendations into a day-wise itinerary.

16. Group geographically nearby attractions on the same day
    to reduce unnecessary travel.

17. Include a sensible morning, afternoon and evening plan.
    Do not invent travel times or opening hours.

18. Consider weather conditions when suggesting outdoor
    activities.

    19. When the user asks for hotel or restaurant
    recommendations, call recommend_hotels_and_restaurants.
    Recommend only establishments returned by the tool.
    Never invent ratings, prices or availability.
"""

agent = Agent(
    model=model,
    tools=[
    get_weather_forecast,
    suggest_packing_list,
    estimate_trip_cost,
    recommend_places,
    recommend_hotels_and_restaurants
],
    system_prompt=system_prompt
)


# --------------------------------------------------
# Local testing
# --------------------------------------------------

if __name__ == "__main__":

    response = agent(
        "I'm going to Goa, India for 3 days. "
        "There will be 3 travellers in total, including me. "
        "Give me a useful travel plan with weather, "
        "packing suggestions, places to visit and estimated budget."
    )

    print("\nTRAVEL PLAN")
    print(response)
