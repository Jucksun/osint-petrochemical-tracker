import os
from pathlib import Path

OUT_DIR = Path(os.getenv("DOW_OUT", "out"))
OUT_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = OUT_DIR / "dow.duckdb"

# SEC requires a descriptive User-Agent: "Your Name you@example.com"
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "")

# Registrants (entities that file with the SEC), each with its OWN CIK.
# Dow Inc. and TDCC file one combined 10-K as co-registrants. The run script checks
# each CIK's name against EDGAR and stops if it does not look like Dow.
ULTIMATE_PARENT_CIK = 1751788  # Dow Inc. (confirmed from sec.gov filing URLs)
SEED_CIKS = [
    1751788,  # Dow Inc.
    29915,    # The Dow Chemical Company (VERIFY on first run; the script prints the EDGAR name)
]
# Add other Dow-family registrants you discover (for example Union Carbide, if it files
# on its own). Do not guess: look the CIK up on EDGAR and add it here.
EXTRA_CIKS: list[int] = []

# Distinctive name fragments for ECHO searches, in addition to Exhibit 21 names.
# Tokens are matched on word boundaries, so "DOW" will not match "WINDOW".
SEED_TOKENS = ["DOW CHEMICAL", "DOW INC", "UNION CARBIDE", "DOW SILICONES", "ROHM AND HAAS"]

STATE_NAMES = {
    "ALABAMA", "ALASKA", "ARIZONA", "ARKANSAS", "CALIFORNIA", "COLORADO", "CONNECTICUT",
    "DELAWARE", "FLORIDA", "GEORGIA", "HAWAII", "IDAHO", "ILLINOIS", "INDIANA", "IOWA",
    "KANSAS", "KENTUCKY", "LOUISIANA", "MAINE", "MARYLAND", "MASSACHUSETTS", "MICHIGAN",
    "MINNESOTA", "MISSISSIPPI", "MISSOURI", "MONTANA", "NEBRASKA", "NEVADA", "NEW HAMPSHIRE",
    "NEW JERSEY", "NEW MEXICO", "NEW YORK", "NORTH CAROLINA", "NORTH DAKOTA", "OHIO",
    "OKLAHOMA", "OREGON", "PENNSYLVANIA", "RHODE ISLAND", "SOUTH CAROLINA", "SOUTH DAKOTA",
    "TENNESSEE", "TEXAS", "UTAH", "VERMONT", "VIRGINIA", "WASHINGTON", "WEST VIRGINIA",
    "WISCONSIN", "WYOMING",
}
