"""Constants for scripts."""
from pathlib import Path

BASE_PATH = Path(__file__).parent.parent / "src/pvcast/data"

PVLIB_INV_NAME = "cec_inverters_pvlib.csv"
PVLIB_MOD_NAME = "cec_modules_pvlib.csv"
SAM_INV_NAME = "cec_inverters_sam.csv"
SAM_MOD_NAME = "cec_modules_sam.csv"

INV_PVLIB_PATH = BASE_PATH / "raw" / PVLIB_INV_NAME
INV_SAM_PATH = BASE_PATH / "raw" / SAM_INV_NAME
MOD_PVLIB_PATH = BASE_PATH / "raw" / PVLIB_MOD_NAME
MOD_SAM_PATH = BASE_PATH / "raw" / SAM_MOD_NAME

# src/pvcast/data/proc
INV_PROC_PATH = BASE_PATH / "proc" / "cec_inverters.csv"
MOD_PROC_PATH = BASE_PATH / "proc" / "cec_modules.csv"
