import pytest
from pytest_metadata.plugin import metadata_key

from chainprobe.client import open_ws


@pytest.fixture(scope="session", autouse=True)
def node_info(network, evm, pytestconfig):
    """Put the node version into the report header."""
    metadata = pytestconfig.stash[metadata_key]
    try:
        if network.wss:
            with open_ws(network.wss) as ws:
                metadata["Node"] = f"{ws.call('system_name')} {ws.call('system_version')}"
                metadata["Peers"] = ws.call("system_health").get("peers")
        else:
            metadata["Node"] = evm.call("web3_clientVersion")
    except Exception as exc:
        metadata["Node"] = f"unavailable ({type(exc).__name__})"
