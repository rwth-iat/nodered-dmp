from dataclasses import dataclass

from nodered_dmp.aas.aas_to_etlpath import parse_aimc
from nodered_dmp.model.etl_path import ETLPath
from nodered_dmp.model.store import ETLPathStore


@dataclass
class SyncResult:
    created: list[ETLPath]
    updated: list[tuple[ETLPath, ETLPath]]  # (before, after)
    deleted: list[ETLPath]


def sync_aas(
    aimc_url: str,
    server_base: str,
    store: ETLPathStore,
    dry_run: bool = False,
) -> SyncResult:
    """
    Parse an AIMC submodel and reconcile the results against the store.

    - Parsed path matches a stored path by (aimc_submodel_id, aimc_idshort_path) → update volatile fields.
    - No match → new ETLPath, saved with a fresh UUID.
    - Stored paths from the same aimc_submodel_id absent from the parsed results → deleted.

    When dry_run=True the diff is computed and returned but the store is not modified.

    Returns a SyncResult describing what changed.
    """
    parsed = parse_aimc(aimc_url, server_base)
    if not parsed:
        return SyncResult(created=[], updated=[], deleted=[])

    aimc_submodel_id = parsed[0].aas.aimc_submodel_id
    parsed_by_aimc_path = {p.aas.aimc_idshort_path: p for p in parsed}

    created: list[ETLPath] = []
    updated: list[tuple[ETLPath, ETLPath]] = []

    for parsed_path in parsed:
        existing = store.find_by_aimc_path(
            parsed_path.aas.aimc_submodel_id, parsed_path.aas.aimc_idshort_path
        )
        if existing:
            before = existing.model_copy(deep=True)
            after = existing.model_copy(deep=True)
            after.extract = parsed_path.extract
            after.transform = parsed_path.transform
            after.load = parsed_path.load
            after.aas = parsed_path.aas
            after.aid = parsed_path.aid
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
        if (
            stored.aas
            and stored.aas.aimc_submodel_id == aimc_submodel_id
            and stored.aas.aimc_idshort_path not in parsed_by_aimc_path
        ):
            if not dry_run:
                store.delete(stored.etl_path_id)
            deleted.append(stored)

    return SyncResult(created=created, updated=updated, deleted=deleted)
