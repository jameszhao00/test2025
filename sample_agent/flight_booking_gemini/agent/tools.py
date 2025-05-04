# agent/tools.py
import datetime
import random
import logging
from typing import List, Dict, Any
from google.genai import types

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

_last_search_call: Dict[str, Any] | None = None
_last_booking_call: Dict[str, Any] | None = None

def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
) -> list[dict]:
    """
    Searches for available flights based on criteria.

    Args:
        origin: The departure airport code (e.g., "SFO").
        destination: The arrival airport code (e.g., "JFK").
        departure_date: The desired departure date (YYYY-MM-DD).

    Returns:
        A list of flight dictionaries, each containing flight_id, airline,
        departure_time, arrival_time, and price. Returns an empty list if no
        flights match or date is invalid.
    """
    global _last_search_call
    args = locals()  # Capture arguments
    log.info(
        f"Tool Executing: Searching flights from {origin} to {destination} on {departure_date}"
    )

    # Simulate database lookup - generate some mock flights
    flights_found = []
    airlines = ["UA", "AA", "DL", "SW"]
    base_price = random.randint(200, 800)

    # Validate date format (basic check)
    try:
        datetime.datetime.strptime(departure_date, "%Y-%m-%d")
    except ValueError:
        log.error("Invalid date format provided to search_flights.")
        result = []  # Return empty list for invalid date
        _last_search_call = {"args": args, "result": result}  # Store state
        return result

    for i in range(random.randint(1, 5)):
        flight_id = f"{random.choice(airlines)}{random.randint(100, 999)}"
        dep_hour = random.randint(6, 21)
        dep_minute = random.choice([0, 15, 30, 45])
        arr_hour = (dep_hour + random.randint(3, 6)) % 24  # Simplified duration
        arr_minute = random.choice([0, 15, 30, 45])
        price = base_price + random.randint(-50, 100)

        departure_time = f"{dep_hour:02d}:{dep_minute:02d}"
        arrival_time = f"{arr_hour:02d}:{arr_minute:02d}"

        # Filter by time preference
        time_match = True

        # Filter by max price
        price_match = True

        if time_match and price_match:
            flights_found.append(
                {
                    "flight_id": flight_id,
                    "airline": flight_id[:2],
                    "departure_time": departure_time,
                    "arrival_time": arrival_time,
                    "price": price,
                }
            )

    log.info(f"Tool Executing: Found {len(flights_found)} flights.")
    _last_search_call = {"args": args, "result": flights_found}  # Store state
    return flights_found


def book_flight(flight_id: str) -> dict:
    """
    Books the flight specified by the flight_id.

    Args:
        flight_id: The unique identifier of the flight to book.

    Returns:
        A dictionary containing the booking confirmation details, including
        booking_id and status. Returns failure status if flight_id is invalid.
    """
    global _last_booking_call
    args = locals()
    log.info(f"Tool Executing: Attempting to book flight {flight_id}")
    result: Dict[str, Any]
    if (
        not flight_id or not isinstance(flight_id, str) or not flight_id.isalnum()
    ):  # Added isalnum check
        log.error("Tool: Invalid flight_id provided for booking.")
        result = {
            "booking_id": None,
            "status": "failed",
            "message": "Invalid or missing flight ID provided.",
        }
        _last_booking_call = {"args": args, "result": result}  # Store state
        return result

    # Simulate booking process
    success = random.choice([True, True, True, False])  # Simulate occasional failures

    if success:
        booking_id = f"BK{random.randint(10000, 99999)}"
        status = "confirmed"
        message = f"Flight {flight_id} booked successfully."
        log.info(
            f"Tool Executing: Booking successful for {flight_id}, ID: {booking_id}"
        )
        result = {"booking_id": booking_id, "status": status, "message": message}
    else:
        log.warning(f"Tool Executing: Booking failed for flight {flight_id}")
        result = {
            "booking_id": None,
            "status": "failed",
            "message": f"Could not book flight {flight_id}. Please try again or select a different flight.",
        }

    _last_booking_call = {"args": args, "result": result}  # Store state
    return result


# --- Functions for Evaluator to Access State ---
def get_last_search_call() -> Dict[str, Any] | None:
    """Returns the args and result of the last search_flights call."""
    return _last_search_call


def get_last_booking_call() -> Dict[str, Any] | None:
    """Returns the args and result of the last book_flight call."""
    return _last_booking_call


def reset_tool_states():
    """Resets the stored state for evaluation runs."""
    global _last_search_call, _last_booking_call
    _last_search_call = None
    _last_booking_call = None
    log.debug("Tool states reset.")


# --- Tool Definitions for Gemini (Manual Function Calling) ---

search_flights_declaration = {
    "name": "search_flights",
    "description": "Searches for available flights based on origin, destination, date, and optional price/time preferences.",
    "parameters": {
        "type": "object",
        "properties": {
            "origin": {
                "type": "string",
                "description": "The departure airport code (e.g., 'SFO').",
            },
            "destination": {
                "type": "string",
                "description": "The arrival airport code (e.g., 'JFK', 'CDG').",
            },
            "departure_date": {
                "type": "string",
                "description": "The desired departure date in YYYY-MM-DD format.",
            },
        },
        "required": ["origin", "destination", "departure_date"],
    },
}

book_flight_declaration = {
    "name": "book_flight",
    "description": "Books a specific flight using its unique flight ID obtained from a search.",
    "parameters": {
        "type": "object",
        "properties": {
            "flight_id": {
                "type": "string",
                "description": "The unique identifier of the flight to book (e.g., 'UA123', 'AA456').",
            },
        },
        "required": ["flight_id"],
    },
}

# --- Dictionary mapping tool names to actual functions ---
TOOL_FUNCTION_MAP = {
    "search_flights": search_flights,
    "book_flight": book_flight,
}

# --- List of Tool Declarations for the SDK ---
# Used when automatic_function_calling is disabled

AGENT_TOOL_DECLARATIONS = [
    types.Tool(
        function_declarations=[search_flights_declaration, book_flight_declaration]
    )
]
