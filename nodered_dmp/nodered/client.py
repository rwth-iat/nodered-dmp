from dataclasses import dataclass

import requests


class FlowNotFoundError(Exception):
    pass


@dataclass
class DeployPreview:
    action: str             # "add" | "replace"
    flow_name: str
    new_node_count: int
    removed_node_count: int # 0 when action == "add"
    other_tab_count: int
    other_node_count: int


def _headers(token: str | None) -> dict:
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def get_flow_nodes(server_base: str, flow_name: str, token: str | None = None) -> list[dict]:
    """
    Fetch all nodes belonging to the named flow tab from a running Node-RED instance.

    Returns the tab node, all nodes in that tab (z == tab_id), and any global
    config nodes (nodes with no z that are not tab or subflow definitions).

    Raises FlowNotFoundError if no tab with that name exists.
    """
    resp = requests.get(f"{server_base}/flows", headers=_headers(token))
    resp.raise_for_status()
    all_nodes: list[dict] = resp.json()

    tab = next(
        (n for n in all_nodes if n.get("type") == "tab" and n.get("label") == flow_name),
        None,
    )
    if tab is None:
        raise FlowNotFoundError(f"No flow named '{flow_name}' found on {server_base}")

    tab_id = tab["id"]
    tab_nodes = [n for n in all_nodes if n.get("z") == tab_id]
    config_nodes = [
        n for n in all_nodes
        if not n.get("z") and n.get("type") not in ("tab", "subflow")
    ]
    return [tab] + tab_nodes + config_nodes


def preview_deploy(
    server_base: str,
    flow_nodes: list[dict],
    flow_name: str,
    token: str | None = None,
) -> DeployPreview:
    """
    Return a DeployPreview describing what deploy_flow would do, without deploying.
    """
    resp = requests.get(f"{server_base}/flows", headers=_headers(token))
    resp.raise_for_status()
    existing: list[dict] = resp.json()

    existing_tab = next(
        (n for n in existing if n.get("type") == "tab" and n.get("label") == flow_name),
        None,
    )

    if existing_tab:
        old_id = existing_tab["id"]
        removed = [n for n in existing if n.get("z") == old_id or n.get("id") == old_id]
        surviving = [n for n in existing if n.get("z") != old_id and n.get("id") != old_id]
        action = "replace"
    else:
        removed = []
        surviving = existing
        action = "add"

    other_tabs = [n for n in surviving if n.get("type") == "tab"]
    other_nodes = [n for n in surviving if n.get("type") != "tab"]

    return DeployPreview(
        action=action,
        flow_name=flow_name,
        new_node_count=len(flow_nodes),
        removed_node_count=len(removed),
        other_tab_count=len(other_tabs),
        other_node_count=len(other_nodes),
    )


def deploy_flow(
    server_base: str,
    flow_nodes: list[dict],
    flow_name: str,
    token: str | None = None,
) -> None:
    """
    Deploy a flow to a running Node-RED instance.

    If a tab named flow_name already exists on the server, its nodes are removed
    and replaced with flow_nodes. All other tabs and their nodes are preserved.
    If no tab with that name exists, the new flow is simply added.
    """
    resp = requests.get(f"{server_base}/flows", headers=_headers(token))
    resp.raise_for_status()
    existing: list[dict] = resp.json()

    existing_tab = next(
        (n for n in existing if n.get("type") == "tab" and n.get("label") == flow_name),
        None,
    )
    if existing_tab:
        old_id = existing_tab["id"]
        existing = [n for n in existing if n.get("z") != old_id and n.get("id") != old_id]

    merged = existing + flow_nodes

    resp = requests.post(
        f"{server_base}/flows",
        json=merged,
        headers={**_headers(token), "Node-RED-Deployment-Type": "full"},
    )
    resp.raise_for_status()
