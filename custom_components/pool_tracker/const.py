"""Constants for Pool Tracker."""

from __future__ import annotations

DOMAIN = "pool_tracker"
PLATFORMS = ["event", "sensor"]

CONF_POOLS = "pools"
CONF_POOL_ID = "pool_id"
CONF_POOL_NAME = "name"
CONF_POOL_VOLUME = "volume"
CONF_POOL_VOLUME_UNIT = "volume_unit"
CONF_POOL_TYPE = "pool_type"
CONF_SURFACE_TYPE = "surface_type"
CONF_SANITIZER_TYPE = "sanitizer_type"
CONF_DEFAULT_TESTING_METHOD = "default_testing_method"
CONF_TYPICALLY_COVERED = "typically_covered"
CONF_WEATHER_ENTITY_ID = "weather_entity_id"
CONF_SUNLIGHT_ENTITY_ID = "sunlight_entity_id"
CONF_RAINFALL_ENTITY_ID = "rainfall_entity_id"
CONF_TEMPERATURE_ENTITY_ID = "temperature_entity_id"
CONF_COVER_ENTITY_ID = "cover_entity_id"
DEFAULT_POOL_ID = "pool"
DEFAULT_POOL_NAME = "Pool"
DEFAULT_POOL_VOLUME_UNIT = "gal"
DEFAULT_TESTING_METHOD = "strips"

SERVICE_LOG_WATER_TEST = "log_water_test"
SERVICE_LOG_CHEMICAL_ADDITION = "log_chemical_addition"
SERVICE_GET_PREDICTION = "get_prediction"

EVENT_RECORD_CREATED = f"{DOMAIN}_record_created"
EVENT_TYPE_CHEMICAL_ADDITION = "chemical_addition"
EVENT_TYPE_WATER_TEST = "water_test"

RECORD_TYPE_WATER_TEST = "water_test"
RECORD_TYPE_CHEMICAL_ADDITION = "chemical_addition"

WATER_READING_FREE_CHLORINE = "free_chlorine"
WATER_READING_PH = "ph"
WATER_READING_TOTAL_ALKALINITY = "total_alkalinity"
WATER_READING_CYA = "cya"
WATER_READING_WATER_CLARITY = "water_clarity"
WATER_TESTING_METHOD = "testing_method"

WATER_CLARITY_OPTIONS = ("clear", "hazy", "cloudy", "green", "other")

NUMERIC_WATER_READINGS = (
    WATER_READING_FREE_CHLORINE,
    WATER_READING_PH,
    WATER_READING_TOTAL_ALKALINITY,
    WATER_READING_CYA,
)

POOL_CONTEXT_ENTITY_KEYS = (
    CONF_WEATHER_ENTITY_ID,
    CONF_SUNLIGHT_ENTITY_ID,
    CONF_RAINFALL_ENTITY_ID,
    CONF_TEMPERATURE_ENTITY_ID,
    CONF_COVER_ENTITY_ID,
)

POOL_VOLUME_UNITS = ("gal", "L")
POOL_TYPES = ("outdoor", "indoor", "spa", "swim_spa", "other")
POOL_SURFACE_TYPES = ("plaster", "vinyl", "fiberglass", "tile", "painted", "other")
POOL_SANITIZER_TYPES = (
    "chlorine",
    "salt_chlorine_generator",
    "bromine",
    "mineral",
    "other",
)
WATER_TESTING_METHODS = (
    "strips",
    "drop_test",
    "digital_meter",
    "photometer",
    "pool_store",
    "other",
)

WATER_TEST_READING_UNITS = {
    WATER_READING_FREE_CHLORINE: "ppm",
    WATER_READING_PH: "pH",
    WATER_READING_TOTAL_ALKALINITY: "ppm",
    WATER_READING_CYA: "ppm",
    WATER_READING_WATER_CLARITY: "description",
}

SELECT_LABELS = {
    "gal": "Gallons",
    "L": "Liters",
    "outdoor": "Outdoor",
    "indoor": "Indoor",
    "spa": "Spa",
    "swim_spa": "Swim spa",
    "plaster": "Plaster",
    "vinyl": "Vinyl",
    "fiberglass": "Fiberglass",
    "tile": "Tile",
    "painted": "Painted",
    "chlorine": "Chlorine",
    "salt_chlorine_generator": "Salt chlorine generator",
    "bromine": "Bromine",
    "mineral": "Mineral",
    "strips": "Test strips",
    "drop_test": "Drop test",
    "digital_meter": "Digital meter",
    "photometer": "Photometer",
    "pool_store": "Pool store",
    "other": "Other",
}
