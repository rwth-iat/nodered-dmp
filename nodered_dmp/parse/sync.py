from dataclasses import dataclass
from typing import Any

from nodered_dmp.model.etl_path import ETLPath
from nodered_dmp.model.store import ETLPathStore
from nodered_dmp.parse.flow_parser import parse_flow


@dataclass
class SyncResult:
    created: list[ETLPath]
    updated: list[tuple[ETLPath, ETLPath]]  # (before, after)
    deleted: list[ETLPath]


def sync_flow(
    nodes: list[dict[str, Any]],
    store: ETLPathStore,
    dry_run: bool = False,
) -> SyncResult:
    """
    Parse a Node-RED flow and reconcile the results against the store.

    - Parsed path matches a stored path by endpoint_node_id → update volatile fields.
    - No match → new ETLPath, saved with a fresh UUID.
    - Stored paths whose endpoint_node_id is absent from the parsed results → deleted.

    When dry_run=True the diff is computed and returned but the store is not modified.

    Returns a SyncResult describing what changed.
    """
    parsed = parse_flow(nodes)
    parsed_by_node_id = {
        p.nodered.endpoint_node_id: p for p in parsed if p.nodered
    }

    created: list[ETLPath] = []
    updated: list[tuple[ETLPath, ETLPath]] = []

    for parsed_path in parsed:
        if not parsed_path.nodered:
            continue
        existing = store.find_by_node_id(parsed_path.nodered.endpoint_node_id)
        if existing:
            before = existing.model_copy(deep=True)
            after = existing.model_copy(deep=True)
            after.extract = parsed_path.extract
            after.transform = parsed_path.transform
            after.load = parsed_path.load
            after.nodered = parsed_path.nodered
            if before != after:
                if not dry_run:
                    store.save(after)
                updated.append((before, after))
        else:
            if not dry_run:
                store.save(parsed_path)
            created.append(parsed_path)

    deleted: list[ETLPath] = []
    for stored in store.load_all():
        if stored.nodered and stored.nodered.endpoint_node_id not in parsed_by_node_id:
            if not dry_run:
                store.delete(stored.etl_path_id)
            deleted.append(stored)

    return SyncResult(created=created, updated=updated, deleted=deleted)
