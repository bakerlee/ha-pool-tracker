"""Constants for Pool Tracker."""

from __future__ import annotations

from enum import StrEnum

from homeassistant.const import UnitOfMass, UnitOfTemperature, UnitOfVolume

DOMAIN = "pool_tracker"
PLATFORMS = ["event", "sensor"]

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
CONF_COVER_ENTITY_ID = "cover_entity_id"
CONF_TRACKED_METRICS = "tracked_metrics"
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


class PoolChemical(StrEnum):
    """Chemicals accepted by the chemical-addition service."""

    DICHLOR = "dichlor"
    TRICHLOR = "trichlor"
    CALCIUM_HYPOCHLORITE = "calcium hypochlorite"
    LIQUID_CHLORINE = "liquid chlorine"
    BLEACH = "bleach"
    MURIATIC_ACID = "muriatic acid"
    SODA_ASH = "soda ash"
    BAKING_SODA = "baking soda"
    CYANURIC_ACID = "cyanuric acid"
    SALT = "salt"
    ALGAECIDE = "algaecide"
    CLARIFIER = "clarifier"
    CALCIUM_HARDNESS_INCREASER = "calcium hardness increaser"


CHEMICAL_OPTIONS = tuple(chemical.value for chemical in PoolChemical)
CHEMICAL_AMOUNT_WEIGHT_UNITS = (
    UnitOfMass.GRAMS,
    UnitOfMass.KILOGRAMS,
    UnitOfMass.OUNCES,
    UnitOfMass.POUNDS,
)
CHEMICAL_AMOUNT_VOLUME_UNITS = (
    UnitOfVolume.MILLILITERS,
    UnitOfVolume.LITERS,
    UnitOfVolume.FLUID_OUNCES,
    UnitOfVolume.GALLONS,
)
CHEMICAL_AMOUNT_INTEGRATION_UNITS = ("Tbsp",)
CHEMICAL_AMOUNT_UNITS = (
    tuple(
        unit.value
        for unit in CHEMICAL_AMOUNT_WEIGHT_UNITS + CHEMICAL_AMOUNT_VOLUME_UNITS
    )
    + CHEMICAL_AMOUNT_INTEGRATION_UNITS
)
CHEMICAL_AMOUNT_UNIT_ALIASES = {
    "tablespoon": "Tbsp",
    "tablespoons": "Tbsp",
    "tbsp": "Tbsp",
}


def normalize_chemical_amount_unit(value: str) -> str:
    """Return the canonical stored chemical amount unit."""
    unit = value.strip()
    return CHEMICAL_AMOUNT_UNIT_ALIASES.get(unit.lower(), unit)


WATER_READING_FREE_CHLORINE = "free_chlorine"
WATER_READING_TOTAL_CHLORINE = "total_chlorine"
WATER_READING_COMBINED_CHLORINE = "combined_chlorine"
WATER_READING_TOTAL_BROMINE = "total_bromine"
WATER_READING_PH = "ph"
WATER_READING_TOTAL_ALKALINITY = "total_alkalinity"
WATER_READING_CALCIUM_HARDNESS = "calcium_hardness"
WATER_READING_TOTAL_HARDNESS = "total_hardness"
WATER_READING_CYA = "cya"
WATER_READING_SALT = "salt"
WATER_READING_TOTAL_DISSOLVED_SOLIDS = "total_dissolved_solids"
WATER_READING_PHOSPHATES = "phosphates"
WATER_READING_COPPER = "copper"
WATER_READING_IRON = "iron"
WATER_READING_WATER_TEMPERATURE = "water_temperature"
WATER_READING_WATER_CLARITY = "water_clarity"
WATER_TESTING_METHOD = "testing_method"

WATER_CLARITY_OPTIONS = ("clear", "hazy", "cloudy", "green", "other")

NUMERIC_WATER_READINGS = (
    WATER_READING_FREE_CHLORINE,
    WATER_READING_TOTAL_CHLORINE,
    WATER_READING_COMBINED_CHLORINE,
    WATER_READING_TOTAL_BROMINE,
    WATER_READING_PH,
    WATER_READING_TOTAL_ALKALINITY,
    WATER_READING_CALCIUM_HARDNESS,
    WATER_READING_TOTAL_HARDNESS,
    WATER_READING_CYA,
    WATER_READING_SALT,
    WATER_READING_TOTAL_DISSOLVED_SOLIDS,
    WATER_READING_PHOSPHATES,
    WATER_READING_COPPER,
    WATER_READING_IRON,
    WATER_READING_WATER_TEMPERATURE,
)

PREDICTED_WATER_READINGS = (
    WATER_READING_FREE_CHLORINE,
    WATER_READING_PH,
    WATER_READING_TOTAL_ALKALINITY,
    WATER_READING_CYA,
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
    WATER_READING_TOTAL_CHLORINE: "ppm",
    WATER_READING_COMBINED_CHLORINE: "ppm",
    WATER_READING_TOTAL_BROMINE: "ppm",
    WATER_READING_PH: "pH",
    WATER_READING_TOTAL_ALKALINITY: "ppm",
    WATER_READING_CALCIUM_HARDNESS: "ppm",
    WATER_READING_TOTAL_HARDNESS: "ppm",
    WATER_READING_CYA: "ppm",
    WATER_READING_SALT: "ppm",
    WATER_READING_TOTAL_DISSOLVED_SOLIDS: "ppm",
    WATER_READING_PHOSPHATES: "ppm",
    WATER_READING_COPPER: "ppm",
    WATER_READING_IRON: "ppm",
    WATER_READING_WATER_TEMPERATURE: UnitOfTemperature.FAHRENHEIT,
    WATER_READING_WATER_CLARITY: "description",
}

WATER_TEST_READING_PRECISION = {
    WATER_READING_FREE_CHLORINE: 2,
    WATER_READING_TOTAL_CHLORINE: 2,
    WATER_READING_COMBINED_CHLORINE: 2,
    WATER_READING_TOTAL_BROMINE: 2,
    WATER_READING_PH: 2,
    WATER_READING_TOTAL_ALKALINITY: 0,
    WATER_READING_CALCIUM_HARDNESS: 0,
    WATER_READING_TOTAL_HARDNESS: 0,
    WATER_READING_CYA: 0,
    WATER_READING_SALT: 0,
    WATER_READING_TOTAL_DISSOLVED_SOLIDS: 0,
    WATER_READING_PHOSPHATES: 2,
    WATER_READING_COPPER: 2,
    WATER_READING_IRON: 2,
    WATER_READING_WATER_TEMPERATURE: 1,
}

WATER_TEST_METRICS = (
    *NUMERIC_WATER_READINGS,
    WATER_READING_WATER_CLARITY,
)


def enabled_water_test_metrics(pool_profile: dict) -> tuple[str, ...]:
    """Return the water-test metrics enabled for a pool profile."""
    configured = pool_profile.get(CONF_TRACKED_METRICS)
    if configured is None:
        return WATER_TEST_METRICS
    return tuple(metric for metric in configured if metric in WATER_TEST_METRICS)


SELECT_LABELS = {
    "dichlor": "Dichlor",
    "trichlor": "Trichlor",
    "calcium hypochlorite": "Calcium hypochlorite",
    "liquid chlorine": "Liquid chlorine",
    "bleach": "Bleach",
    "muriatic acid": "Muriatic acid",
    "soda ash": "Soda ash",
    "baking soda": "Baking soda",
    "cyanuric acid": "Cyanuric acid",
    "salt": "Salt",
    "algaecide": "Algaecide",
    "clarifier": "Clarifier",
    "calcium hardness increaser": "Calcium hardness increaser",
    "g": "Grams",
    "kg": "Kilograms",
    "oz": "Ounces",
    "lb": "Pounds",
    "mL": "Milliliters",
    "Tbsp": "Tablespoons",
    "fl. oz.": "Fluid ounces",
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
    WATER_READING_FREE_CHLORINE: "Free chlorine",
    WATER_READING_TOTAL_CHLORINE: "Total chlorine",
    WATER_READING_COMBINED_CHLORINE: "Combined chlorine",
    WATER_READING_TOTAL_BROMINE: "Total bromine",
    WATER_READING_PH: "pH",
    WATER_READING_TOTAL_ALKALINITY: "Total alkalinity",
    WATER_READING_CALCIUM_HARDNESS: "Calcium hardness",
    WATER_READING_TOTAL_HARDNESS: "Total hardness",
    WATER_READING_CYA: "CYA/stabilizer",
    WATER_READING_SALT: "Salt",
    WATER_READING_TOTAL_DISSOLVED_SOLIDS: "Total dissolved solids",
    WATER_READING_PHOSPHATES: "Phosphates",
    WATER_READING_COPPER: "Copper",
    WATER_READING_IRON: "Iron",
    WATER_READING_WATER_TEMPERATURE: "Water temperature",
    WATER_READING_WATER_CLARITY: "Water clarity",
}
