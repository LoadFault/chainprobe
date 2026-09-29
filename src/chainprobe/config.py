from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Network:
    name: str
    rpc: str
    wss: str | None = None
    chain_id: int | None = None
    block_time: float | None = None
    max_finality_seconds: float | None = None
    logs_range_limit: int | None = None


NETWORKS = {
    "orbinum": Network(
        name="orbinum",
        rpc="https://rpc-1.testnet.orbinum.io",
        wss="wss://rpc-1.testnet.orbinum.io",
        chain_id=2700,
        block_time=6,
        max_finality_seconds=30,
        logs_range_limit=1024,
    ),
    # EVM execution layer on Canton, values from docs.zenith.network/zenith-testnet
    "zenith": Network(
        name="zenith",
        rpc="https://rpc.testnet.zenith.network/",
        chain_id=936485,
        block_time=5,
        max_finality_seconds=10,
    ),
}


def resolve_network(
    name: str, rpc: str | None = None, wss: str | None = None, chain_id: int | None = None
) -> Network:
    """Take a preset and apply command-line overrides on top of it.

    Custom endpoints drop every preset expectation, since they belong to a different network.
    """
    if rpc or wss:
        return Network(name="custom", rpc=rpc or NETWORKS[name].rpc, wss=wss, chain_id=chain_id)
    network = NETWORKS[name]
    return replace(network, chain_id=chain_id if chain_id is not None else network.chain_id)
