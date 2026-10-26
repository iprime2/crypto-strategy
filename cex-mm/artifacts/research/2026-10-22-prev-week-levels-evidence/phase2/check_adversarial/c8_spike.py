"""C8: strict single-bar spike: the touch bar trades >= 50 bps beyond L and closes back inside L."""
import json, pickle, sys
import numpy as np
D = "/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/research3/p2/check_adv"
sys.path.insert(0, D)
import adv_lib as A  # noqa
res = pickle.load(open(f"{D}/events_adv.pkl", "rb"))
out = {}
for panel in ("OT", "OX"):
    ev, wk = res[(panel, "base")]
    for ctl in ("real", "P1"):
        e = ev[(ev.status == "ok") & (ev.horizon == "4h") & (ev.control == ctl)]
        s = e.s.to_numpy()
        exc = np.where(s > 0, e.tb_h / e.L - 1, 1 - e.tb_l / e.L) * 1e4
        cb = np.where(s > 0, e.tb_c / e.L - 1, 1 - e.tb_c / e.L) * 1e4
        spike = (exc >= 50) & (cb < 0)
        out[f"{panel}_{ctl}"] = {"n": int(len(e)), "spike_share": float(spike.mean()), "spike_n": int(spike.sum()),
                                 "spike_gross_mean": float(e.gross[spike].mean()),
                                 "close_beyond_L_ge_50bp_share": float((cb >= 50).mean()),
                                 "close_beyond_L_ge_50bp_gross_mean": float(e.gross[cb >= 50].mean()),
                                 "share_of_gross_sum_from_close_ge_50bp": float(e.gross[cb >= 50].sum() / e.gross.sum())}
        print(panel, ctl, {k: round(v, 4) for k, v in out[f"{panel}_{ctl}"].items()})
json.dump(out, open(f"{D}/c8_spike.json", "w"), indent=1)
