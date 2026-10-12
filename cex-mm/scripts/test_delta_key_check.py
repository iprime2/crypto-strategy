"""delta_key_check.py against a local mock of Delta's API that verifies the HMAC signature.

    cd cex-mm/scripts && python3 -m unittest -v test_delta_key_check
"""
import hashlib
import hmac
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "delta_key_check.py"
KEY, SECRET = "test-key", "test-secret-123"
STATE = {"leverage": "2", "whitelisted": True}


class FakeDelta(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path, _, query = self.path.partition("?")
        if path == "/v2/products/ADAUSD":
            return self.send(200, {"success": True, "result": {"id": 2391, "contract_value": "1"}})
        signed = f"GET{self.headers.get('timestamp')}{path}{'?' + query if query else ''}"
        want = hmac.new(SECRET.encode(), signed.encode(), hashlib.sha256).hexdigest()
        if self.headers.get("api-key") != KEY or self.headers.get("signature") != want:
            return self.send(401, {"success": False, "error": {"code": "Signature Mismatch"}})
        if not STATE["whitelisted"]:
            return self.send(401, {"success": False, "error": {"code": "ip_not_whitelisted_for_api_key"}})
        if path == "/v2/wallet/balances":
            return self.send(200, {"success": True, "meta": {"net_equity": "280.12"}, "result": []})
        if path == "/v2/products/2391/orders/leverage":
            return self.send(200, {"success": True, "result": {"leverage": STATE["leverage"], "margin_mode": "cross"}})
        if path == "/v2/positions/margined" and query == "product_ids=2391":
            return self.send(200, {"success": True, "result": []})
        self.send(404, {"success": False, "error": {"code": "not_found"}})


class DeltaKeyCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeDelta)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        STATE.update(leverage="2", whitelisted=True)

    def run_check(self, env_text):
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as f:
            f.write(env_text)
        env = {**os.environ, "DELTA_REST_BASE": self.base, "NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1"}
        p = subprocess.run([sys.executable, "-I", str(SCRIPT), f.name], capture_output=True, text=True, env=env)
        os.unlink(f.name)
        out = p.stdout + p.stderr
        self.assertNotIn(KEY, out, "the key must never be printed")
        self.assertNotIn(SECRET, out, "the secret must never be printed")
        return p.returncode, out

    GOOD = f"DELTA_MAINNET_API_KEY={KEY}\nDELTA_MAINNET_API_SECRET={SECRET}\n"

    def test_good_key_passes(self):
        rc, out = self.run_check(self.GOOD)
        self.assertEqual(rc, 0, out)
        self.assertIn("net equity 280.12", out)
        self.assertIn("leverage ADAUSD 2x", out)

    def test_wrong_variable_names_fail(self):
        rc, out = self.run_check(f"DISM_DELTA_MAINNET_API_KEY={KEY}\nDISM_DELTA_MAINNET_API_SECRET={SECRET}\n")
        self.assertNotEqual(rc, 0)
        self.assertIn("DISM_DELTA_MAINNET_API_KEY", out)

    def test_wrong_secret_fails(self):
        rc, out = self.run_check(f"DELTA_MAINNET_API_KEY={KEY}\nDELTA_MAINNET_API_SECRET=wrong\n")
        self.assertEqual(rc, 1)
        self.assertIn("Signature Mismatch", out)

    def test_leverage_above_cap_fails(self):
        STATE["leverage"] = "100"
        rc, out = self.run_check(self.GOOD)
        self.assertEqual(rc, 1)
        self.assertIn("FAIL leverage ADAUSD 100x", out)

    def test_ip_not_whitelisted_fails(self):
        STATE["whitelisted"] = False
        rc, out = self.run_check(self.GOOD)
        self.assertEqual(rc, 1)
        self.assertIn("ip_not_whitelisted", out)


if __name__ == "__main__":
    unittest.main()
