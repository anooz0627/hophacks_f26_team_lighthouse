from __future__ import annotations

import networkx as nx

from ..models import (GraphEdge, GraphNode, LatLng, PlanGraph, RejectedResource, Resource, ServiceType,
                      TransitData, UserConstraints)
from .travel import to_point, travel_options

ORIGIN = "__origin__"

NEED_LABEL = {
    ServiceType.emergency_housing: "Emergency Housing",
    ServiceType.food: "Food",
    ServiceType.long_term_assistance: "Longer-term Assistance",
}


def build_travel_graph(origin: LatLng, resources: list[Resource], uc: UserConstraints,
                       transit: TransitData) -> nx.DiGraph:
    g = nx.DiGraph()
    g.add_node(ORIGIN, point=to_point(origin))
    for r in resources:
        g.add_node(r.id, point=(r.lat, r.lng), resource=r)
    budget = uc.constraints.budget_usd
    nodes = list(g.nodes)
    for u in nodes:
        for v in nodes:
            if u == v or v == ORIGIN:
                continue
            options = travel_options(g.nodes[u]["point"], g.nodes[v]["point"], uc.constraints, transit, budget)
            if options:
                leg = min(options, key=lambda item: (item.duration_min, item.cost_usd))
                g.add_edge(u, v, leg=leg, options=options, weight=leg.duration_min)
    return g


def build_plan_graph(uc: UserConstraints, eligible: list[Resource], rejected: list[RejectedResource],
                     selected_ids: list[str], legs_between: list[tuple[str, str, str]],
                     all_resources: dict[str, Resource]) -> PlanGraph:
    nodes: list[GraphNode] = [GraphNode(id=ORIGIN, label="You", kind="origin", selected=True)]
    edges: list[GraphEdge] = []
    need_types = [n.type for n in uc.needs]
    for t in need_types:
        nodes.append(GraphNode(id=f"need:{t.value}", label=NEED_LABEL[t], kind="need", service=t, selected=True))
    sel = set(selected_ids)
    for r in eligible:
        nodes.append(GraphNode(id=r.id, label=r.name, kind="resource", service=r.service, selected=r.id in sel))
        edges.append(GraphEdge(source=r.id, target=f"need:{r.service.value}", kind="provides",
                               selected=r.id in sel))
        if r.eligibility.requires_id:
            edges.append(GraphEdge(source=r.id, target="req:photo_id", kind="requires", label="Photo ID"))
    included = {node.id for node in nodes}
    for rj in rejected:
        if rj.resource_id in included:
            continue
        r = all_resources[rj.resource_id]
        nodes.append(GraphNode(id=r.id, label=r.name, kind="resource", service=r.service, eligible=False))
        edges.append(GraphEdge(source=r.id, target=f"need:{r.service.value}", kind="provides", label=rj.reason))
    if any(e.target == "req:photo_id" for e in edges):
        nodes.append(GraphNode(id="req:photo_id", label="Photo ID", kind="need"))
    for u, v, label in legs_between:
        edges.append(GraphEdge(source=u, target=v, kind="reachable_by", label=label, selected=True))
    return PlanGraph(nodes=nodes, edges=edges)
