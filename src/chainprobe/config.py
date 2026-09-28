from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Network:
    name: str
    rpc: str
    wss: str
    chain_id: int | None = None


NETWORKS = {
    "orbinum": Network(
        name="orbinum",
        rpc="https://rpc-1.testnet.orbinum.io",
        wss="wss://rpc-1.testnet.orbinum.io",
        chain_id=2700,
    ),
}


def resolve_network(
    name: str, rpc: str | None = None, wss: str | None = None, chain_id: int | None = None
) -> Network:
    """Take a preset and apply command-line overrides on top of it."""
    network = NETWORKS[name]
    if rpc or wss:
        network = replace(network, name="custom", chain_id=None)
    return replace(
        network,
        rpc=rpc or network.rpc,
        wss=wss or network.wss,
        chain_id=chain_id if chain_id is not None else network.chain_id,
    )
