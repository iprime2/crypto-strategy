# Piped to python3 on the VM over tailscale ssh (read-only; prints JSON, writes nothing):
#   tailscale ssh ubuntu@dism-tokyo "python3 - '<windows json>'" < vm_fetch_runner.py > vm_fetch_funding_3passes.json
# Runs ON the VM via stdin: imports the deployed trend_paper.fetch_funding (no main, no writes) and calls it for each
# journal window, three passes, printing JSON to stdout. Public candles only.
import sys, json, time, os
sys.path.insert(0, os.path.expanduser("~/crypto-strategy/cex-mm/scripts"))
import trend_paper as tp
wins = json.loads(sys.argv[1])
out = {"started": time.time(), "passes": []}
for p in range(3):
    res = []
    for since, until in wins:
        res.append(tp.fetch_funding(since, until))
    out["passes"].append(res)
out["ended"] = time.time()
print(json.dumps(out))
