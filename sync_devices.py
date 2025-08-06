from api_librenms import get_librenms_devices
from api_netbox import nb_get, nb_post
from device_type_importer import import_device_type_if_exists
from device_utils import resolve_device_type, validate_device
from config import DEFAULT_SITE_SLUG, DEFAULT_ROLE_SLUG


def get_site_id(slug):
    resp = nb_get("dcim/sites/", slug=slug)
    if resp.get("count"):
        return resp["results"][0]["id"]
    raise ValueError(f"No existe el sitio: {slug}")

def get_role_id(slug):
    resp = nb_get("dcim/device-roles/", slug=slug)
    if resp.get("count"):
        return resp["results"][0]["id"]
    raise ValueError(f"No existe el role: {slug}")

def sync_devices():
    devices = get_librenms_devices()
    print(f"LibreNMS → {len(devices)} devices")
    try:
        site_id = get_site_id(DEFAULT_SITE_SLUG)
        role_id = get_role_id(DEFAULT_ROLE_SLUG)
    except Exception as e:
        print(f"Error: {e}")
        return
    for d in devices:
        if not validate_device(d):
            print("SKIP inválido", d)
            continue
        lid = d.get("device_id")
        nm = d.get("hostname") or d.get("sysName")
        vendor, model = resolve_device_type(d)
        dtid = import_device_type_if_exists(vendor, model)
        if dtid is None:
            print(f"SKIP sin device_type {nm} ({vendor}/{model})")
            continue

        cf = {"cf_librenms_id": lid}
        existe = nb_get("dcim/devices/", **cf).get("count", 0)
        if existe:
            print(f"= Ya existe {nm}")
            continue
        pl = {
            "name": nm,
            "device_type": dtid,
            "role": role_id,
            "site": site_id,
            "status": "active",
            "custom_fields": {"librenms_id": str(lid)},
        }
        nb_post("dcim/devices/", pl)
        print(f"+ Creado {nm} ({lid}) con device_type {dtid}")
if __name__ == "__main__":
    sync_devices()
