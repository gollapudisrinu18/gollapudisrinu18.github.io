"""Overview architecture diagrams for the home page, generated as inline SVG.

Each diagram is drawn from the project source and docs/architecture.md:
  delivery        projects/01-aks-delivery-platform  (pipelines/, scripts/deploy_with_rollback.sh)
  infrastructure  projects/02-azure-hub-spoke-terraform  (modules/, envs/lab)
  reliability     projects/03-aks-observability-sre-lab  (service/, prometheus/rules, docs/postmortem.md)
Colours come from CSS classes (dg-*) so the diagrams follow the light and dark themes.
"""
from html import escape

W = 960


def _text_lines(x, y, lines, cls, size, weight=None, anchor="middle", gap=None):
    gap = gap or round(size * 1.3)
    out = []
    for i, line in enumerate(lines):
        w = f' font-weight="{weight}"' if weight else ""
        out.append(f'<text class="{cls}" x="{x}" y="{y + i * gap}" font-size="{size}"{w} text-anchor="{anchor}">{escape(line)}</text>')
    return "".join(out)


def box(x, y, w, h, title, sub=(), kind="", step=None):
    """A rounded node with a bold title and up to three sub lines."""
    cls = "dg-box" + (f" dg-{kind}" if kind else "")
    out = [f'<g class="dg-node"{f" data-step={chr(34)}{step}{chr(34)}" if step else ""}>',
           f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" rx="10"/>']
    lines = [title] if isinstance(title, str) else list(title)
    total = len(lines) * 19 + len(sub) * 17
    ty = y + (h - total) / 2 + 14
    out.append(_text_lines(x + w / 2, ty, lines, "dg-title", 15, 600, gap=19))
    if sub:
        out.append(_text_lines(x + w / 2, ty + len(lines) * 19 + 1, sub, "dg-sub", 13, gap=17))
    out.append("</g>")
    return "".join(out)


def group(x, y, w, h, label, sub=None, kind="zone"):
    out = [f'<rect class="dg-{kind}" x="{x}" y="{y}" width="{w}" height="{h}" rx="14"/>',
           f'<text class="dg-group" x="{x + 14}" y="{y + 24}" font-size="14" font-weight="700">{escape(label)}</text>']
    if sub:
        out.append(f'<text class="dg-sub" x="{x + 14}" y="{y + 42}" font-size="12.5">{escape(sub)}</text>')
    return "".join(out)


def arrow(d, label=None, lx=None, ly=None, kind="", both=False, anchor="middle"):
    cls = "dg-edge" + (f" dg-edge-{kind}" if kind else "")
    marker = "url(#MK-arrow-fail)" if kind == "fail" else "url(#MK-arrow)"
    start = f' marker-start="{marker}"' if both else ""
    out = f'<path class="{cls}" d="{d}" marker-end="{marker}"{start}/>'
    if label:
        out += (f'<text class="dg-label{" dg-label-fail" if kind == "fail" else ""}" x="{lx}" y="{ly}" '
                f'font-size="12.5" text-anchor="{anchor}">{escape(label)}</text>')
    return out


def svg(name, h, title, desc, body):
    return (f'<svg class="arch-svg" viewBox="0 0 {W} {h}" role="img" aria-labelledby="dg-{name}-t dg-{name}-d" '
            f'xmlns="http://www.w3.org/2000/svg" font-family="Inter, system-ui, sans-serif">'
            f'<title id="dg-{name}-t">{escape(title)}</title><desc id="dg-{name}-d">{escape(desc)}</desc>'
            '<defs>'
            '<marker id="' + name + '-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            '<path class="dg-head" d="M0,0 L10,5 L0,10 z"/></marker>'
            '<marker id="' + name + '-arrow-fail" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            '<path class="dg-head-fail" d="M0,0 L10,5 L0,10 z"/></marker>'
            '</defs>' + body.replace("#MK-", "#" + name + "-") + '</svg>')


def delivery():
    b = []
    # row 1: change -> validation -> build -> registry
    b.append(box(20, 24, 190, 76, "Source change", ["push or pull request", "to main"], step="delivery"))
    b.append(box(260, 24, 200, 76, "Azure Pipelines", ["validate: pytest", "PRs stop here"], kind="accent"))
    b.append(box(510, 24, 200, 76, "Build image", ["az acr build", "tag = Build ID"]))
    b.append(box(760, 24, 180, 76, "ACR", ["one image, promoted", "unchanged"], kind="store"))
    b.append(arrow("M210,62 H254"))
    b.append(arrow("M460,62 H504"))
    b.append(arrow("M710,62 H754"))
    # promotion path from ACR to Dev
    b.append(arrow("M850,100 V134 H115 V164", "same image tag promoted through each environment", 480, 127))
    # row 2: environments
    sub = ["helm upgrade --wait", "smoke test"]
    b.append(box(20, 168, 190, 84, "AKS orders-dev", sub))
    b.append(box(260, 168, 200, 84, "AKS orders-qa", sub))
    b.append(box(510, 168, 200, 84, "Approval gate", ["check on the", "orders-prod environment"], kind="gate"))
    b.append(box(760, 168, 180, 84, "AKS orders-prod", sub))
    b.append(arrow("M210,210 H254"))
    b.append(arrow("M460,210 H504"))
    b.append(arrow("M710,210 H754"))
    # rollback path
    b.append('<rect class="dg-fail-zone" x="20" y="306" width="920" height="62" rx="10"/>')
    b.append(_text_lines(480, 332, ["Smoke test fails → helm rollback to the revision recorded before deploy → re-run smoke test"],
                         "dg-title dg-fail-text", 14.5, 600))
    b.append(_text_lines(480, 354, ["The stage is marked failed, so later environments are never deployed"], "dg-sub", 13))
    for x in (115, 360, 850):
        b.append(arrow(f"M{x},252 V300", kind="fail"))
    b.append(f'<text class="dg-label dg-label-fail" x="606" y="282" font-size="12.5" text-anchor="middle">on smoke-test failure</text>')
    return svg("delivery", 384, "Delivery architecture: AKS Delivery Platform (portfolio lab)",
               "A source change triggers Azure Pipelines, which validates with pytest and builds one image in ACR tagged with the "
               "build ID. The same image is promoted through AKS orders-dev, orders-qa and, after an approval gate, orders-prod. "
               "Each deployment runs helm upgrade --wait and a smoke test; a failed smoke test triggers helm rollback to the "
               "recorded revision and fails the stage so later environments are not deployed.", "".join(b))


def infrastructure():
    b = []
    b.append(group(270, 14, 420, 120, "Hub VNet  10.0.0.0/16", "Terraform module: hub-network"))
    b.append(box(286, 72, 192, 46, "snet-shared-services", [], kind="subnet"))
    b.append(box(484, 72, 190, 46, "snet-management", [], kind="subnet"))
    # spokes
    b.append(group(20, 196, 360, 196, "Spoke app  10.1.0.0/16", "security boundary: own VNet + NSG"))
    b.append(box(38, 252, 324, 58, "snet-workload", ["NSG: 443 from hub · deny Internet"], kind="subnet"))
    b.append(box(38, 320, 324, 58, "snet-private-endpoints", ["pe-blob → 10.1.2.4 · NSG: 443 from VNet"], kind="accent", step="infrastructure"))
    b.append(group(580, 196, 360, 196, "Spoke data  10.2.0.0/16", "security boundary: own VNet + NSG"))
    b.append(box(598, 252, 324, 58, "snet-workload", ["NSG: 443 from hub · deny Internet"], kind="subnet"))
    b.append(box(598, 320, 324, 58, "snet-private-endpoints", ["NSG: 443 from VNet"], kind="subnet"))
    # peering
    b.append(arrow("M310,134 L230,192", "peering", 248, 158, both=True, anchor="end"))
    b.append(arrow("M650,134 L730,192", "peering", 712, 158, both=True, anchor="start"))
    # private dns zone
    b.append(box(398, 214, 164, 80, ["Private DNS zone"], ["privatelink.blob", ".core.windows.net"], kind="store"))
    b.append(arrow("M480,214 V140", "VNet link", 488, 182, kind="link", anchor="start"))
    b.append(arrow("M398,254 H386", kind="link"))
    b.append(arrow("M562,254 H574", kind="link"))
    b.append(f'<text class="dg-label" x="480" y="312" font-size="12.5" text-anchor="middle">linked to hub, app, data</text>')
    # storage via private link
    b.append(box(330, 436, 300, 56, "Storage account", ["public network access disabled"], kind="store"))
    b.append(arrow("M200,378 V464 H324", "Private Link", 262, 456))
    return svg("infrastructure", 506, "Infrastructure architecture: Terraform hub-and-spoke (portfolio lab)",
               "A hub VNet (10.0.0.0/16) is peered both ways with an app spoke (10.1.0.0/16) and a data spoke (10.2.0.0/16). "
               "Each spoke is its own VNet with NSG-protected subnets; the app workload subnet allows 443 from the hub and denies "
               "Internet. A private endpoint in the app spoke (10.1.2.4) reaches a storage account whose public access is "
               "disabled. The privatelink.blob private DNS zone is linked to the hub, app and data VNets so names resolve to "
               "the private endpoint.", "".join(b))


def reliability():
    b = []
    b.append(box(20, 70, 200, 92, "checkout-api", ["OpenTelemetry SDK", "latency histogram"], step="reliability"))
    b.append(box(280, 24, 230, 76, "Metrics", ["Prometheus scrape", "recording rules"]))
    b.append(box(280, 132, 230, 76, "Traces", ["OTLP → OTel Collector", "one span per dependency"]))
    b.append(arrow("M220,100 L274,70"))
    b.append(arrow("M220,132 L274,164"))
    b.append(box(570, 40, 370, 92, "SLO burn-rate alert", ["99% of checkouts < 300 ms over 30 days", "page at 14.4x · ticket at 6x"], kind="gate"))
    b.append(arrow("M510,66 H564"))
    # response row
    b.append(box(20, 282, 280, 92, "Investigate", ["span timings show", "inventory.lookup ≈ 800 ms"], kind="accent"))
    b.append(box(340, 282, 280, 92, "Mitigate", ["enable cache fallback", "burn rate back to 0x"]))
    b.append(box(660, 282, 280, 92, "Postmortem", ["blameless timeline, budget used,", "action items"]))
    b.append(arrow("M755,132 V244 H160 V276", "page to on-call", 640, 237))
    b.append(arrow("M330,208 L250,276", "traces", 282, 230, kind="link", anchor="end"))
    b.append(arrow("M300,328 H334"))
    b.append(arrow("M620,328 H654"))
    return svg("reliability", 388, "Reliability architecture: AKS Observability and SRE Incident Lab (portfolio lab)",
               "checkout-api emits Prometheus metrics and OpenTelemetry traces. Prometheus recording rules feed a latency SLO "
               "(99% of checkouts under 300 ms over 30 days) with burn-rate alerts that page at 14.4x and open a ticket at 6x. "
               "The page leads to investigation using span timings, which point to inventory.lookup; mitigation enables the "
               "cache fallback; a blameless postmortem records the timeline, error budget used and action items.", "".join(b))


def all_diagrams():
    return {"delivery": delivery(), "infrastructure": infrastructure(), "reliability": reliability()}
