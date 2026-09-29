from chainprobe.config import NETWORKS, resolve_network


def test_preset_is_returned_unchanged():
    assert resolve_network("zenith") == NETWORKS["zenith"]


def test_chain_id_override_keeps_preset():
    network = resolve_network("orbinum", chain_id=1)
    assert network.chain_id == 1
    assert network.wss == NETWORKS["orbinum"].wss


def test_custom_rpc_drops_preset_expectations():
    network = resolve_network("orbinum", rpc="http://localhost:8545")
    assert network.name == "custom"
    assert network.wss is None
    assert network.block_time is None
    assert network.logs_range_limit is None
