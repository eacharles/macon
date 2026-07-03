from ... import remote_sync
from .base import make_table_group

test_named_group = make_table_group("test_named", remote_sync.test_named, "Manage TestNamed table")

test_ref_group = make_table_group("test_ref", remote_sync.test_ref, "Manage TestRef table")

test_list_pair_group = make_table_group(
    "test_list_pair", remote_sync.test_list_pair, "Manage TestListPair table"
)
