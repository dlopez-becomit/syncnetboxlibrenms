from api_librenms import get_librenms_devices
from api_netbox import nb_get, nb_post
from device_type_importer import import_device_type_if_exists
from device_utils import resolve_device_type, validate_device
from config import DEFAULT_SITE_SLUG, DEFAULT_ROLE_SLUG


def get_platform_id(slug: str | None) -> int | None:
    """Return NetBox platform ID for given slug if it exists."""
    if not slug:
        return None
    resp = nb_get("dcim/platforms/", slug=slug)
    if resp.get("count"):
        return resp["results"][0]["id"]
    return None

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
            print(f"SKIP {nm}: Sin device_type válido (vendor={vendor} model={model})")
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

        if d.get("serial"):
            pl["serial"] = d["serial"]
        if d.get("asset_tag"):
            pl["asset_tag"] = d["asset_tag"]
        if d.get("os"):
            plat_id = get_platform_id(d.get("os"))
            if plat_id:
                pl["platform"] = plat_id
        ip4 = d.get("ip") or d.get("ipv4") or d.get("ip4") or d.get("primary_ip")
        if ip4:
            pl["primary_ip4"] = ip4
        if d.get("notes"):
            pl["comments"] = d["notes"]

        extra_cf_map = {
            "hardware": "librenms_hardware",
            "location": "librenms_location",
            "purpose": "librenms_purpose",
        }
        for key, cf_name in extra_cf_map.items():
            val = d.get(key)
            if val:
                pl.setdefault("custom_fields", {})[cf_name] = str(val)

        nb_post("dcim/devices/", pl)
        print(f"+ Creado {nm} ({lid}) con device_type {dtid}")
if __name__ == "__main__":
    sync_devices()
