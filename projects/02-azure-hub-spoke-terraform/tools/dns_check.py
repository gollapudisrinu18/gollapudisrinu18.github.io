#!/usr/bin/env python3
"""Explain how a name resolves from a VNet that uses Azure-provided DNS.

Input is the `dns_model` Terraform output (or a scenario file in the same
shape). The model follows the Azure Private Link DNS behaviour:

  1. <account>.blob.core.windows.net is a public CNAME to
     <account>.privatelink.blob.core.windows.net
  2. If the querying VNet is linked to the private DNS zone
     privatelink.blob.core.windows.net, the A record in that zone answers
     with the private endpoint IP.
  3. If the VNet is NOT linked, resolution continues in public DNS and
     returns the storage account's public IP. With public network access
     disabled, the client then gets HTTP 403 instead of reaching the
     private endpoint.

  terraform output -json dns_model > model.json
  python tools/dns_check.py --model model.json --from-vnet app \
      --name <account>.blob.core.windows.net --expect private
"""
import argparse
import ipaddress
import json
import sys

PUBLIC_PLACEHOLDER_IP = "20.60.0.10"  # synthetic public storage IP for the lab


def load_model(path):
    with open(path) as fh:
        data = json.load(fh)
    # `terraform output -json dns_model` returns the value directly;
    # `terraform output -json` returns {"dns_model": {"value": ...}}.
    if "dns_model" in data:
        data = data["dns_model"]["value"]
    return data


def resolve(model, from_vnet, name):
    if from_vnet not in model["vnets"]:
        raise ValueError(f"unknown VNet '{from_vnet}'. Known: {', '.join(model['vnets'])}")
    trace = []
    name = name.lower().rstrip(".")
    target = model.get("public_cnames", {}).get(name)
    if target:
        trace.append(f"{name} -> CNAME {target} (public DNS)")
        name = target

    for zone, zdata in model["zones"].items():
        if not name.endswith("." + zone):
            continue
        host = name[: -(len(zone) + 1)]
        if from_vnet in zdata["linked_vnets"]:
            ip = zdata["records"].get(host)
            if ip is None:
                trace.append(f"{name}: zone {zone} is linked to '{from_vnet}' but has no A record for '{host}'")
                return {"answer": None, "kind": "NXDOMAIN", "trace": trace}
            trace.append(f"{name} -> A {ip} (private zone {zone}, linked to '{from_vnet}')")
            return {"answer": ip, "kind": "private", "trace": trace}
        trace.append(f"zone {zone} is NOT linked to VNet '{from_vnet}'; Azure DNS falls back to public resolution")
        trace.append(f"{name} -> A {PUBLIC_PLACEHOLDER_IP} (public endpoint)")
        return {"answer": PUBLIC_PLACEHOLDER_IP, "kind": "public", "trace": trace}

    trace.append(f"{name}: no private zone matches; public resolution")
    return {"answer": PUBLIC_PLACEHOLDER_IP, "kind": "public", "trace": trace}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--from-vnet", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--expect", choices=["private", "public"])
    args = ap.parse_args(argv)

    model = load_model(args.model)
    result = resolve(model, args.from_vnet, args.name)
    print(f"Resolving {args.name} from VNet '{args.from_vnet}'")
    for line in result["trace"]:
        print("  " + line)
    if result["kind"] == "private":
        assert ipaddress.ip_address(result["answer"]).is_private
        print(f"RESULT: private endpoint {result['answer']} - traffic stays on the VNet")
    elif result["kind"] == "public":
        print(f"RESULT: public IP {result['answer']} - private endpoint bypassed; "
              "storage has public access disabled, so requests fail with HTTP 403")
    else:
        print("RESULT: NXDOMAIN - private endpoint DNS record missing")
    if args.expect:
        ok = result["kind"] == args.expect
        print(f"CHECK: expected {args.expect} -> {'PASS' if ok else 'FAIL'}")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
