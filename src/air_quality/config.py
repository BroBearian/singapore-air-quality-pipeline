import os

from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

DATA_GOV_API_KEY = os.getenv("DATA_GOV_API_KEY") or None
DAYS_BACK = int(os.getenv("DAYS_BACK", "1"))

PM25_URL = "https://api-open.data.gov.sg/v2/real-time/api/pm25"
PSI_URL = "https://api-open.data.gov.sg/v2/real-time/api/psi"

VALID_REGIONS = {"central", "north", "south", "east", "west"}
