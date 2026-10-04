from chainprobe.client import EvmClient

e = EvmClient("https://rpc.testnet.zenith.network/", rps=4)
latest = e.block_number()
print("latest:", latest)

prev = None
for n in range(latest - 160, latest + 1):
    b = e.get_block(n)
    ts, txs = int(b["timestamp"], 16), len(b["transactions"])
    used, limit = int(b["gasUsed"], 16), int(b["gasLimit"], 16)
    gap = ts - prev if prev else 0
    if gap != 5 or n % 20 == 0:
        print(f"#{n} gap={gap}s txs={txs} gas={used}/{limit} ({used / limit:.0%})")
    prev = ts

for method, params in [("txpool_status", []), ("eth_getBlockTransactionCountByNumber", ["pending"])]:
    try:
        print(method, e.call(method, params))
    except Exception as exc:
        print(method, "->", exc)