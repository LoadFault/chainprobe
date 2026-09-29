import html

import pytest
from pytest_metadata.plugin import metadata_key

from chainprobe.client import EvmClient, open_ws
from chainprobe.config import NETWORKS, Network, resolve_network


def pytest_addoption(parser):
    group = parser.getgroup("chainprobe")
    group.addoption("--network", default="orbinum", choices=list(NETWORKS), help="network preset")
    group.addoption("--rpc", help="EVM JSON-RPC URL (overrides the preset)")
    group.addoption("--wss", help="Substrate WebSocket URL (overrides the preset)")
    group.addoption("--chain-id", type=int, help="expected EVM chain id")
    group.addoption("--rps", type=float, default=2.0, help="max requests per second")
    group.addoption("--monitor-duration", type=int, default=120, help="seconds to watch the block stream")


def pytest_configure(config):
    opt = config.getoption
    config.network = resolve_network(opt("--network"), opt("--rpc"), opt("--wss"), opt("--chain-id"))

    metadata = config.stash[metadata_key]
    metadata.clear()
    metadata["Network"] = config.network.name
    metadata["EVM RPC"] = config.network.rpc
    metadata["Substrate WSS"] = config.network.wss or "not used"


@pytest.fixture(scope="session")
def network(pytestconfig) -> Network:
    return pytestconfig.network


@pytest.fixture(scope="session")
def evm(network, pytestconfig):
    client = EvmClient(network.rpc, rps=pytestconfig.getoption("--rps"))
    yield client
    client.close()


@pytest.fixture
def ws(network):
    if network.wss is None:
        pytest.skip("network has no Substrate WebSocket endpoint")
    with open_ws(network.wss) as client:
        yield client


def pytest_html_report_title(report):
    report.title = "chainprobe report"


def pytest_html_results_table_header(cells):
    cells.insert(2, "<th>Metrics</th>")


def pytest_html_results_table_row(report, cells):
    metrics = ", ".join(f"{name}={value}" for name, value in report.user_properties)
    cells.insert(2, f"<td>{html.escape(metrics)}</td>")
