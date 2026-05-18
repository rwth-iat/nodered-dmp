from basyx.aas import model
from basyx.aas.adapter import aasx

from basyx.aas.adapter import json as aas_json

# Let's read the AASX package file, we have just written.
# We'll use a fresh ObjectStore and SupplementaryFileContainer to read AAS objects and auxiliary files into.
new_object_store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
new_file_store = aasx.DictSupplementaryFileContainer()

# Again, we need to use the AASXReader as a context manager (or call `.close()` in the end) to make sure the AASX
# package file is properly closed when we are finished.
with aasx.AASXReader("AID_AIMC_Example.aasx") as reader:
    # Read all contained AAS objects and all referenced auxiliary files
    reader.read_into(object_store=new_object_store,
                     file_store=new_file_store)

    # We can also read the metadata
    new_meta_data = reader.get_core_properties()

    # We could also read the thumbnail image, using `reader.get_thumbnail()`

