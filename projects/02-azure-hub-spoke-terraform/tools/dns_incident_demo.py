#!/usr/bin/env python3
"""Local walkthrough of the private DNS misconfiguration and its fix.

Uses scenarios/broken.json and scenarios/fixed.json, which have the same
shape as `terraform output -json dns_model` for envs/lab with and without
misconfig.tfvars.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dns_check  # noqa: E402

ROOT = os.path.join(HERE, "..")
NAME = "sthslabdemo01.blob.core.windows.net"


def section(title):
    print(f"\n=== {title} ===", flush=True)


def main():
    section("1. Broken state: terraform apply -var-file=misconfig.tfvars")
    print("Symptom reported: app in spoke 'app' gets HTTP 403 AuthorizationFailure from blob storage")
    broken = dns_check.main(["--model", os.path.join(ROOT, "scenarios/broken.json"),
                             "--from-vnet", "app", "--name", NAME, "--expect", "private"])

    section("2. Diagnose: compare with a VNet that works")
    dns_check.main(["--model", os.path.join(ROOT, "scenarios/broken.json"),
                    "--from-vnet", "data", "--name", NAME])
    print("\nDiagnosis: the privatelink.blob zone has links for hub and data only.")
    print("On Azure: az network private-dns link vnet list -g rg-hslab-network "
          "-z privatelink.blob.core.windows.net -o table")

    section("3. Fix: link the app spoke (terraform apply without misconfig.tfvars)")
    print("  + module.blob_dns.azurerm_private_dns_zone_virtual_network_link.this[\"app\"]")
    fixed = dns_check.main(["--model", os.path.join(ROOT, "scenarios/fixed.json"),
                            "--from-vnet", "app", "--name", NAME, "--expect", "private"])

    section("Result")
    ok = broken == 1 and fixed == 0
    print("DEMO RESULT:", "PASS - app spoke now resolves the private endpoint" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
