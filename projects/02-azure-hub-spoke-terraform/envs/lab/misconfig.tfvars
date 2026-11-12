# Reproduces the lab incident: the app spoke is not linked to the
# privatelink.blob zone, so clients in that spoke resolve the storage
# account to its public endpoint.
dns_linked_spokes = ["data"]
