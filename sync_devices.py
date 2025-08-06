from api_librenms import get_librenms_devices, get_librenms_device_ips
from api_netbox import nb_get, nb_post, nb_patch
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
        dev = nb_post("dcim/devices/", pl)
        print(f"+ Creado {nm} ({lid}) con device_type {dtid}")

        nb_id = dev.get("id")
        ips = get_librenms_device_ips(lid)
        primary4_id = None
        primary6_id = None
        for ip in ips:
            ifname = ip.get("ifName") or ip.get("ifname") or ip.get("port_label")
            address = ip.get("address") or ip.get("ip")
            if not (ifname and address and nb_id):
                continue
            iface = nb_get("dcim/interfaces/", device_id=nb_id, name=ifname)
            if not iface.get("count"):
                continue
            iface_id = iface["results"][0]["id"]
            if "/" not in address:
                address = f"{address}/128" if ":" in address else f"{address}/32"
            dup = nb_get("ipam/ip-addresses/", address=address)
            if dup.get("count"):
                ip_id = dup["results"][0]["id"]
            else:
                payload_ip = {
                    "address": address,
                    "status": ip.get("status") or "active",
                    "assigned_object_type": "dcim.interface",
                    "assigned_object_id": iface_id,
                }
                created_ip = nb_post("ipam/ip-addresses/", payload_ip)
                ip_id = created_ip.get("id")
            if ":" in address:
                if not primary6_id:
                    primary6_id = ip_id
            else:
                if not primary4_id:
                    primary4_id = ip_id
        payload = {}
        if primary4_id:
            payload["primary_ip4"] = primary4_id
        if primary6_id:
            payload["primary_ip6"] = primary6_id
        if payload:
            nb_patch(f"dcim/devices/{nb_id}/", payload)
if __name__ == "__main__":
    sync_devices()
