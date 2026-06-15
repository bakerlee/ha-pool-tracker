"""Constants for Pool Tracker."""

from __future__ import annotations

DOMAIN = "pool_tracker"
PLATFORMS = ["sensor"]

CONF_POOLS = "pools"
CONF_POOL_ID = "pool_id"
CONF_POOL_NAME = "name"
DEFAULT_POOL_ID = "pool"
DEFAULT_POOL_NAME = "Pool"

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

WATER_TEST_READING_UNITS = {
    WATER_READING_FREE_CHLORINE: "ppm",
    WATER_READING_PH: "pH",
    WATER_READING_TOTAL_ALKALINITY: "ppm",
    WATER_READING_CYA: "ppm",
    WATER_READING_WATER_CLARITY: "description",
}
