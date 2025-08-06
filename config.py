import os
from dotenv import load_dotenv

load_dotenv()

LIBRENMS_URL = os.getenv("LIBRENMS_URL")
LIBRENMS_TOKEN = os.getenv("LIBRENMS_TOKEN")
NETBOX_URL = os.getenv("NETBOX_URL")
NETBOX_TOKEN = os.getenv("NETBOX_TOKEN")
DEFAULT_SITE_SLUG = os.getenv("DEFAULT_SITE_SLUG")
DEFAULT_ROLE_SLUG = os.getenv("DEFAULT_ROLE_SLUG")
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"