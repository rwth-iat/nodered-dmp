from tinydb import TinyDB, where

from nodered_dmp.model.etl_path import ETLPath


class ETLPathStore:
    def __init__(self, path: str = "etl_paths.json"):
        self.db = TinyDB(path)

    def save(self, path: ETLPath) -> None:
        self.db.upsert(path.model_dump(), where("etl_path_id") == path.etl_path_id)

    def load_all(self) -> list[ETLPath]:
        return [ETLPath.model_validate(d) for d in self.db.all()]

    def find_by_node_id(self, node_id: str) -> ETLPath | None:
        doc = self.db.get(where("nodered").test(
            lambda v: v is not None and v.get("endpoint_node_id") == node_id
        ))
        return ETLPath.model_validate(doc) if doc else None

    def find_by_aimc_path(self, aimc_submodel_id: str, aimc_idshort_path: str) -> ETLPath | None:
        doc = self.db.get(
            where("aas").test(
                lambda v: v is not None
                and v.get("aimc_submodel_id") == aimc_submodel_id
                and v.get("aimc_idshort_path") == aimc_idshort_path
            )
        )
        return ETLPath.model_validate(doc) if doc else None

    def delete(self, etl_path_id: str) -> None:
        self.db.remove(where("etl_path_id") == etl_path_id)
