import requests
import yaml
import os
import re
import ipaddress
from config import NETBOX_URL, NETBOX_TOKEN, DRY_RUN
from device_utils import find_in_tree, TREE, ensure_slug

HEADERS = {"Authorization": f"Token {NETBOX_TOKEN}", "Content-Type": "application/json"}

def nb_get(endpoint, **params):
    url = f"{NETBOX_URL}api/{endpoint}"
    resp = requests.get(url, params=params, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    return resp.json()

def nb_post(endpoint, payload):
    if DRY_RUN:
        print(f"[DRY_RUN] POST {endpoint} -> {payload}")
        return {}
    url = f"{NETBOX_URL}api/{endpoint}"
    resp = requests.post(url, json=payload, headers=HEADERS, timeout=60)
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        print("ERROR en nb_post:")
        print("Request:", url)
        print("Payload:", payload)
        print("Status:", resp.status_code)
        print("Respuesta:", resp.text)
        raise
    return resp.json()


def get_ip_address_id(address: str | None):
    if not address:
        return None
    if "/" in address:
        addr = address
    else:
        try:
            ip_obj = ipaddress.ip_address(address)
        except ValueError:
            return None
        suffix = "32" if ip_obj.version == 4 else "128"
        addr = f"{address}/{suffix}"
    resp = nb_get("ipam/ip-addresses/", address=addr)
    if resp.get("count"):
        return resp["results"][0]["id"]
    created = nb_post("ipam/ip-addresses/", {"address": addr, "status": "active"})
    return created.get("id")

def get_or_create_manufacturer_id(slug: str):
    slug = (slug or "").strip().lower()
    resp = nb_get("dcim/manufacturers/", slug=slug)
    if resp.get("count", 0):
        return resp["results"][0]["id"]
    data = {"name": slug.capitalize(), "slug": slug}
    try:
        created = nb_post("dcim/manufacturers/", data)
        return created.get("id")
    except requests.HTTPError:
        resp = nb_get("dcim/manufacturers/", slug=slug)
        if resp.get("count", 0):
            return resp["results"][0]["id"]
        raise

def get_device_type_id(vendor: str, fname: str):
    vendor = vendor.lower().strip()
    slug_key = fname.strip().lower()
    if not vendor or not slug_key or not TREE:
        return None
    q = nb_get("dcim/device-types/", slug=slug_key)
    if q.get("count", 0):
        return q["results"][0]["id"]
    relpath, suggestions = find_in_tree(vendor, slug_key)
    if not relpath:
        if suggestions:
            print(f"No encontró '{slug_key}'. Sugerencias:")
            for idx, path in enumerate(suggestions, 1):
                print(f"  {idx}) {path}")
            gen_idx = len(suggestions) + 1
            print(f"  {gen_idx}) [GENÉRICO] Crear tipo de dispositivo genérico")
            choice = input(f"Elige número (1-{gen_idx}) o ENTER para saltar: ")
            if choice.isdigit():
                sel = int(choice) - 1
                if 0 <= sel < len(suggestions):
                    relpath = suggestions[sel]
                elif sel == len(suggestions):
                    man_id = get_or_create_manufacturer_id("generic")
                    check = nb_get("dcim/device-types/", slug="generic")
                    if check.get('count'):
                        return check["results"][0]["id"]
                    data = {
                        "manufacturer": man_id,
                        "model": "generic",
                        "slug": "generic"
                    }
                    if DRY_RUN:
                        print("DRY-IMPORT GENERIC", data)
                        return 0
                    created = nb_post("dcim/device-types/", data)
                    return created.get("id")
        if not relpath:
            print(f"Descartado '{slug_key}' (sin matching)")
            return None
    url = f"https://raw.githubusercontent.com/netbox-community/devicetype-library/master/{relpath}"
    print(f"Importando device-type → {url}")
    raw_data = None
    for attempt in range(5):
        try:
            resp = requests.get(url, timeout=20)
            if resp.status_code == 200:
                raw_data = yaml.safe_load(resp.text)
                break
        except requests.RequestException:
            pass
    if raw_data is None:
        print(f"No se pudo descargar {url} tras 5 intentos")
        return None
    filename = os.path.basename(relpath)
    base = filename[:-5]
    tmp = base.replace('+', '-plus')
    tmp = re.sub(r"[\s_]+", "-", tmp)
    clean_slug = re.sub(r"[^a-zA-Z0-9\-]", "", tmp).lower().strip("-")
    data = {
        "manufacturer": get_or_create_manufacturer_id(vendor),
        "model": raw_data.get("model"),
        "slug": clean_slug
    }
    if DRY_RUN:
        print("DRY-IMPORT", data)
        return 0
    try:
        created = nb_post("dcim/device-types/", data)
        return created.get("id")
    except Exception as e:
        print(f"ERROR al crear device-type {clean_slug}: {e}")
        return None