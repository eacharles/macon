
from .. import local_async
from .base import create_table_router


test_named_router = create_table_router("test_named", local_async.test_named)

test_ref_router = create_table_router("test_ref", local_async.test_ref_router)

test_list_pair_router = create_table_router("test_list_pair", local_async.test_list_pair)
