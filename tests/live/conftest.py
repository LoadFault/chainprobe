import pytest
from pytest_metadata.plugin import metadata_key

from chainprobe.client import open_ws


@pytest.fixture(scope="session", autouse=True)
def node_info(network, pytestconfig):
    """Put the node version and peer count into the report header."""
    metadata = pytestconfig.stash[metadata_key]
    try:
        with open_ws(network.wss) as ws:
            metadata["Node"] = f"{ws.call('system_name')} {ws.call('system_version')}"
            metadata["Peers"] = ws.call("system_health").get("peers")
    except Exception as exc:
        metadata["Node"] = f"unavailable ({type(exc).__name__})"
