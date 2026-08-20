"""Capstone: Travel Assistant Agent (Modules 1 & 2)."""

from strands import Agent, tool
from strands.models.bedrock import BedrockModel
from strands_tools import calculator


@tool
def get_weather_forecast(city: str, days: int) -> dict:
    """Get the weather forecast for a city over a number of days."""
    forecasts = {
        "goa": {
            "high_c": 32,
            "low_c": 26,
            "conditions": "humid, occasional showers"
        },
        "bangalore": {
            "high_c": 27,
            "low_c": 18,
            "conditions": "mild, light evening rain"
        },
        "jaipur": {
            "high_c": 38,
            "low_c": 25,
            "conditions": "hot and dry"
        },
        "manali": {
            "high_c": 14,
            "low_c": 3,
            "conditions": "cold, chance of snow"
        },
    }

    data = forecasts.get(
        city.lower(),
        {
            "high_c": 28,
            "low_c": 20,
            "conditions": "moderate"
        }
    )

    return {
        "city": city,
        "days": days,
        **data
    }


@tool
def suggest_packing_list(
    high_c: int,
    low_c: int,
    days: int,
    conditions: str
) -> list:
    """Suggest what to pack based on temperatures and weather."""

    items = [
        f"{days + 1} sets of clothes",
        "toiletries",
        "phone charger"
    ]

    if high_c >= 30:
        items += [
            "light cotton clothing",
            "sunscreen",
            "sunglasses",
            "reusable water bottle"
        ]

    if low_c <= 15:
        items += [
            "warm jacket",
            "thermal layer"
        ]
    elif low_c <= 22:
        items += [
            "light jacket for evenings"
        ]

    if "rain" in conditions.lower() or "shower" in conditions.lower():
        items += [
            "compact umbrella",
            "quick-dry footwear"
        ]

    if "snow" in conditions.lower():
        items += [
            "gloves",
            "woollen cap",
            "waterproof boots"
        ]

    return items


@tool
def estimate_trip_cost(
    city: str,
    days: int,
    travellers: int = 1
) -> dict:
    """Estimate the cost of a trip in Indian rupees."""

    per_night = {
        "goa": 3500,
        "bangalore": 3000,
        "jaipur": 2500,
        "manali": 2800
    }

    stay = per_night.get(city.lower(), 3000) * days
    food = 1200 * days * travellers
    local_travel = 800 * days

    total = stay + food + local_travel

    return {
        "city": city,
        "days": days,
        "travellers": travellers,
        "stay_inr": stay,
        "food_inr": food,
        "local_travel_inr": local_travel,
        "total_inr": total,
    }


model = BedrockModel(
    model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0"
)

agent = Agent(
    model=model,
    tools=[
        get_weather_forecast,
        suggest_packing_list,
        estimate_trip_cost,
        calculator
    ],
    system_prompt=(
        "You are a practical travel assistant. "
        "When asked about a trip: check the weather first, "
        "then suggest what to pack based on that weather, "
        "then estimate the cost. "
        "Always say whether the trip fits the user's budget, "
        "and keep advice concise."
    ),
)


if __name__ == "__main__":
    response = agent(
        "I'm going to Goa for 3 days with 2 friends. "
        "My budget is 20000 rupees. "
        "What should I pack, and does it fit my budget?"
    )

    print(response)