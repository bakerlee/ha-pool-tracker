"""Constants for Pool Tracker."""

from __future__ import annotations

DOMAIN = "pool_tracker"
PLATFORMS = ["sensor"]
DEFAULT_ENTRY_TITLE = "Pool Tracker"

CONF_POOLS = "pools"
CONF_POOL_ID = "pool_id"
CONF_POOL_NAME = "name"
CONF_POOL_VOLUME = "volume"
CONF_POOL_VOLUME_UNIT = "volume_unit"
CONF_POOL_TYPE = "pool_type"
CONF_SURFACE_TYPE = "surface_type"
CONF_SANITIZER_TYPE = "sanitizer_type"
CONF_DEFAULT_TESTING_METHOD = "default_testing_method"
DEFAULT_POOL_ID = "pool"
DEFAULT_POOL_NAME = "Pool"
DEFAULT_POOL_VOLUME_UNIT = "gal"
DEFAULT_TESTING_METHOD = "strips"

SERVICE_LOG_WATER_TEST = "log_water_test"
SERVICE_LOG_CHEMICAL_ADDITION = "log_chemical_addition"

EVENT_RECORD_CREATED = f"{DOMAIN}_record_created"

RECORD_TYPE_WATER_TEST = "water_test"
RECORD_TYPE_CHEMICAL_ADDITION = "chemical_addition"

WATER_READING_FREE_CHLORINE = "free_chlorine"
WATER_READING_PH = "ph"
WATER_READING_TOTAL_ALKALINITY = "total_alkalinity"
WATER_READING_CYA = "cya"
WATER_READING_WATER_CLARITY = "water_clarity"
WATER_TESTING_METHOD = "testing_method"

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
