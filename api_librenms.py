import requests
from config import LIBRENMS_URL, LIBRENMS_TOKEN


def _headers():
    return {"X-Auth-Token": LIBRENMS_TOKEN}


def get_librenms_devices():
    headers = _headers()
    url = f"{LIBRENMS_URL}/api/v0/devices?limit=0"
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json().get("devices", [])


def get_librenms_device_ips(device_id):
    """Return list of IP addresses for a LibreNMS device."""
    headers = _headers()
    url = f"{LIBRENMS_URL}/api/v0/devices/{device_id}/ip"
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json().get("addresses", [])
