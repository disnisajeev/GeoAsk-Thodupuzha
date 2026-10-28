
import json
import math
import re

from qwen_service import client, QWEN_MODEL


ALLOWED_LAYERS = {
    "education",
    "healthcare",
    "pharmacies",
    "food_services",
    "green_spaces",
    "buildings",
    "landuse",
    "roads",
    "shops",
    "transport",
    "waterways",
}


LAYER_MAP = {
    "school": "education",
    "schools": "education",
    "college": "education",
    "colleges": "education",
    "educational institution": "education",
    "educational institutions": "education",
    "hospital": "healthcare",
    "hospitals": "healthcare",
    "clinic": "healthcare",
    "clinics": "healthcare",
    "healthcare facility": "healthcare",
    "healthcare facilities": "healthcare",
    "pharmacy": "pharmacies",
    "pharmacies": "pharmacies",
    "restaurant": "food_services",
    "restaurants": "food_services",
    "food outlet": "food_services",
    "food outlets": "food_services",
    "park": "green_spaces",
    "parks": "green_spaces",
    "green space": "green_spaces",
    "green spaces": "green_spaces",
    "road": "roads",
    "roads": "roads",
    "shop": "shops",
    "shops": "shops",
    "building": "buildings",
    "buildings": "buildings",
    "waterway": "waterways",
    "waterways": "waterways",
    "transport": "transport",
    "transport location": "transport",
    "transport locations": "transport",
    "landuse": "landuse",
    "land use": "landuse",
}


SPATIAL_TERMS = re.compile(
    r"\b("
    r"near|nearby|within|distance|around|buffer|"
    r"intersect|intersection|overlap|nearest|closest|"
    r"farthest|farther|less than|more than|"
    r"kilometres?|kilometers?|metres?|meters?|km"
    r")\b",
    re.IGNORECASE,
)


LIST_INTENT = re.compile(
    r"\b(show|list|display|get|view)\b",
    re.IGNORECASE,
)


def _unsupported_plan(explanation: str) -> dict:
    """Return a consistent unsupported-query plan."""
    return {
        "operation": "unsupported",
        "target_layer": "buildings",
        "reference_layer": None,
        "distance_m": None,
        "explanation": explanation,
    }


def try_simple_list_query(user_query: str):
    """
    Create a plan directly for unambiguous listing queries.

    Simple listing requests do not need an LLM call.
    Spatial or ambiguous requests are sent to Qwen3.
    """
    query = re.sub(
        r"[^a-z0-9\s]",
        " ",
        user_query.lower(),
    )
    query = " ".join(query.split())

    # Do not bypass the planner for spatial queries.
    if SPATIAL_TERMS.search(query):
        return None

    if not LIST_INTENT.search(query):
        return None

    padded_query = f" {query} "
    matches = []

    # Match longer phrases before shorter aliases.
    for alias in sorted(
        LAYER_MAP,
        key=len,
        reverse=True,
    ):
        if f" {alias} " in padded_query:
            matches.append(
                (alias, LAYER_MAP[alias])
            )

    if not matches:
        return None

    longest_length = len(matches[0][0])

    longest_matches = [
        item
        for item in matches
        if len(item[0]) == longest_length
    ]

    matched_layers = {
        layer
        for _, layer in longest_matches
    }

    # Avoid guessing when the query is ambiguous.
    if len(matched_layers) != 1:
        return None

    target_layer = next(iter(matched_layers))

    print(
        "[QUERY PLANNER] Simple listing query; "
        "skipping Qwen3."
    )

    return {
        "operation": "list_features",
        "target_layer": target_layer,
        "reference_layer": None,
        "distance_m": None,
        "explanation": (
            f"Displaying all available features in the "
            f"{target_layer} layer."
        ),
    }


def plan_query(user_query: str) -> dict:
    """
    Convert a natural-language question into a validated GIS plan.

    Simple listing queries use a local fast path.
    Other supported queries use Qwen3.
    """

    if (
        not isinstance(user_query, str)
        or not user_query.strip()
    ):
        return _unsupported_plan(
            "Please enter a GIS query."
        )

    user_query = user_query.strip()

    # Fast path: avoid LLM inference for simple listing queries.
    simple_plan = try_simple_list_query(user_query)

    if simple_plan is not None:
        return simple_plan

    schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "list_features",
                    "within_distance",
                    "unsupported",
                ],
            },
            "target_layer": {
                "type": "string",
                "enum": sorted(ALLOWED_LAYERS),
            },
            "reference_layer": {
                "type": ["string", "null"],
                "enum": sorted(ALLOWED_LAYERS) + [None],
            },
            "distance_m": {
                "type": ["number", "null"],
            },
            "explanation": {
                "type": "string",
            },
        },
        "required": [
            "operation",
            "target_layer",
            "reference_layer",
            "distance_m",
            "explanation",
        ],
    }

    prompt = f"""
Plan a GIS query for Thodupuzha.

Available layers and meanings:
- education: schools, colleges, educational institutions
- healthcare: hospitals, clinics, healthcare facilities
- pharmacies: pharmacies
- food_services: restaurants, food outlets
- green_spaces: parks, green spaces
- buildings: buildings
- landuse: land-use areas
- roads: roads
- shops: shops
- transport: transport locations
- waterways: waterways

Return only the requested JSON object.

Rules:
1. Displaying or listing features means list_features.
2. Proximity or distance queries mean within_distance.
3. In a proximity query, target_layer is the feature type
   the user wants to find.
4. reference_layer is the feature type it must be near.
5. Convert kilometres to metres.
6. Preserve the requested distance accurately.
7. If proximity is requested without a distance, use 500
   metres and explain the assumption.
8. For list_features, reference_layer and distance_m are null.
9. If the requested operation cannot be represented, use unsupported.
10. Never invent layers, distances, results, or feature counts.
11. Only create a plan; do not execute GIS operations.
12. Use exact layer identifiers.
13. Never substitute an unrelated layer for an unavailable one.
14. For unsupported requests, reference_layer and distance_m
    must be null.

Examples:

Question: Show all schools
Plan: {{"operation":"list_features",
"target_layer":"education","reference_layer":null,
"distance_m":null,"explanation":"Show schools"}}

Question: Find schools within 500 metres of hospitals
Plan: {{"operation":"within_distance",
"target_layer":"education","reference_layer":"healthcare",
"distance_m":500,"explanation":"Schools near hospitals"}}

Question: Find shops within 2 km of roads
Plan: {{"operation":"within_distance",
"target_layer":"shops","reference_layer":"roads",
"distance_m":2000,"explanation":"Shops near roads"}}

Question: Show all airports
Plan: {{"operation":"unsupported",
"target_layer":"buildings","reference_layer":null,
"distance_m":null,"explanation":"Airports are unavailable"}}

User question: {user_query}
"""

    print("[QUERY PLANNER] Sending query to Qwen3...")

    response = client.chat(
        model=QWEN_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Convert GIS questions into validated "
                    "structured query plans. Follow the schema "
                    "and rules exactly. Do not include reasoning."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        format=schema,
        think=False,
        stream=False,
        options={
            "temperature": 0,
            "num_predict": 128,
        },
    )

    raw = (
        response.message.content or ""
    ).strip()

    if not raw:
        raise ValueError(
            "Qwen3 returned an empty query plan."
        )

    try:
        plan = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Qwen3 returned invalid JSON for the query plan."
        ) from exc

    if not isinstance(plan, dict):
        raise ValueError(
            "The query plan must be a JSON object."
        )

    required_fields = {
        "operation",
        "target_layer",
        "reference_layer",
        "distance_m",
        "explanation",
    }

    if not required_fields.issubset(plan):
        raise ValueError(
            "The query plan is missing required fields."
        )

    operation = plan["operation"]
    target = plan["target_layer"]
    reference = plan["reference_layer"]
    distance = plan["distance_m"]
    explanation = plan["explanation"]

    if operation not in {
        "list_features",
        "within_distance",
        "unsupported",
    }:
        raise ValueError("Invalid operation.")

    if target not in ALLOWED_LAYERS:
        raise ValueError("Invalid target layer.")

    if (
        reference is not None
        and reference not in ALLOWED_LAYERS
    ):
        raise ValueError("Invalid reference layer.")

    if not isinstance(explanation, str):
        raise ValueError(
            "The explanation must be a string."
        )

    if operation == "list_features":
        if reference is not None or distance is not None:
            raise ValueError(
                "List queries must not include distance parameters."
            )

    elif operation == "within_distance":
        if reference is None or reference == target:
            raise ValueError(
                "A distinct reference layer is required."
            )

        if (
            not isinstance(distance, (int, float))
            or isinstance(distance, bool)
            or not math.isfinite(distance)
            or not 0 < distance <= 100000
        ):
            raise ValueError(
                "Distance must be between 0 and 100000 metres."
            )

        distance = float(distance)

    elif operation == "unsupported":
        reference = None
        distance = None

    return {
        "operation": operation,
        "target_layer": target,
        "reference_layer": reference,
        "distance_m": distance,
        "explanation": explanation[:300],
    }
