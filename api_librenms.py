import requests
from config import LIBRENMS_URL, LIBRENMS_TOKEN


def get_librenms_devices():
    headers = {"X-Auth-Token": LIBRENMS_TOKEN}
    url = f"{LIBRENMS_URL}/api/v0/devices?limit=0"
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json().get("devices", [])


def get_librenms_device_ports(device_id):
    headers = {"X-Auth-Token": LIBRENMS_TOKEN}
    url = f"{LIBRENMS_URL}/api/v0/devices/{device_id}/ports?limit=0"
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json().get("ports", [])

