#!/usr/bin/env python3
"""Premamulu OTC - local data server for Termux.

Logs in to your IQ Option DEMO account, reads OTC candles and serves them, together
with the Premamulu OTC web app, at http://localhost:8080 on this phone only.

Safety:
  * READ-ONLY. This program contains no code that can place, change or close trades.
  * Your password is only sent to IQ Option (auth.iqoption.com) over verified HTTPS.
  * The server listens on 127.0.0.1, so other devices on your Wi-Fi cannot reach it.

Run:  python server.py            (asks for email and password, nothing is saved)
      python server.py --demo-data (fake candles, to try the app without logging in)
"""
import getpass
import json
import math
import os
import random
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "web")
UA = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36"
AUTH_URL = "https://auth.iqoption.com/api/v2/login"
WS_URL = "wss://iqoption.com/echo/websocket"
CANDLE_SECONDS = 60  # 1-minute candles: OTC expiries are 2, 3 and 5 minutes

# IQ Option asset ids for OTC pairs (from the iqoptionapi constants table)
ASSETS = {"EURUSD-OTC": 76, "EURGBP-OTC": 77, "USDCHF-OTC": 78, "EURJPY-OTC": 79, "NZDUSD-OTC": 80,
          "GBPUSD-OTC": 81, "GBPJPY-OTC": 84, "USDJPY-OTC": 85, "AUDCAD-OTC": 86}

STATIC = {"/": ("index.html", "text/html; charset=utf-8"), "/index.html": ("index.html", "text/html; charset=utf-8"),
          "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
          "/sw.js": ("sw.js", "text/javascript; charset=utf-8"), "/icon-192.png": ("icon-192.png", "image/png"),
          "/icon-512.png": ("icon-512.png", "image/png"), "/apple-touch-icon.png": ("apple-touch-icon.png", "image/png")}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def load_config():
    """Optional otc/config.env with IQ_EMAIL, IQ_PASSWORD, PORT. Environment variables override it."""
    cfg = {}
    path = os.path.join(HERE, "config.env")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("IQ_EMAIL", "IQ_PASSWORD", "PORT"):
        if os.environ.get(k):
            cfg[k] = os.environ[k]
    return cfg


class IQClient:
    """Minimal read-only IQ Option client: login, keep-alive, get-candles. Nothing else."""

    def __init__(self, email, password):
        import requests  # noqa: F401  (checked early so the error message is clear)
        import websocket  # noqa: F401
        self.email, self.password = email, password
        self.ssid = None
        self.ws = None
        self.ready = threading.Event()
        self.auth_ok = None
        self.lock = threading.Lock()  # one candle request at a time
        self.reply = None
        self.reply_evt = threading.Event()
        self.server_ms = None
        self.status = "starting"

    def login(self):
        import requests
        r = requests.post(AUTH_URL, data={"identifier": self.email, "password": self.password},
                          headers={"User-Agent": UA}, timeout=25)
        ssid = r.cookies.get("ssid")
        if not ssid:
            try:
                body = r.json()
            except ValueError:
                body = {"message": r.text[:200]}
            code = str(body.get("code", "")) + " " + str(body.get("message", body))
            if "verify" in code.lower() or "2fa" in code.lower():
                raise RuntimeError("This account uses 2-step verification. Turn it off for the demo login, then try again.")
            raise RuntimeError("Login failed: " + code.strip()[:200])
        self.ssid = ssid
        log("Logged in to IQ Option.")

    def _on_open(self, ws):
        ws.send(json.dumps({"name": "ssid", "msg": self.ssid, "request_id": ""}))

    def _on_message(self, ws, raw):
        try:
            m = json.loads(raw)
        except ValueError:
            return
        name = m.get("name")
        if name == "timeSync":
            self.server_ms = m.get("msg")
        elif name == "heartbeat":
            ws.send(json.dumps({"name": "heartbeat", "request_id": "",
                                "msg": {"heartbeatTime": m.get("msg"), "userTime": int(time.time() * 1000)}}))
        elif name in ("profile", "authenticated"):
            if m.get("msg") is False:
                self.auth_ok = False
            else:
                if self.auth_ok is not True:
                    bal = []
                    if name == "profile" and isinstance(m.get("msg"), dict):
                        bal = [b.get("type") for b in m["msg"].get("balances", []) if isinstance(b, dict)]
                    log("Connected." + (" Practice (demo) balance found." if 4 in bal else ""))
                self.auth_ok = True
            self.ready.set()
        elif name == "candles":
            msg = m.get("msg") or {}
            self.reply = msg.get("candles") if isinstance(msg, dict) else None
            self.reply_evt.set()

    def _on_close(self, ws, *a):
        self.status = "disconnected"
        self.ready.clear()

    def _on_error(self, ws, err):
        log("Connection error:", str(err)[:160])

    def connect(self):
        import websocket
        if not self.ssid:
            self.login()
        self.ready.clear()
        self.auth_ok = None
        self.ws = websocket.WebSocketApp(WS_URL, header=["User-Agent: " + UA, "Origin: https://iqoption.com"],
                                         on_open=self._on_open, on_message=self._on_message,
                                         on_close=self._on_close, on_error=self._on_error)
        threading.Thread(target=self.ws.run_forever, kwargs={"ping_interval": 30, "ping_timeout": 10},
                         daemon=True).start()
        if not self.ready.wait(25):
            raise RuntimeError("IQ Option did not answer. Check your internet connection.")
        if self.auth_ok is False:  # old session expired: log in again once
            self.ssid = None
            self.close()
            self.login()
            return self.connect()
        self.status = "connected"

    def close(self):
        try:
            self.ws and self.ws.close()
        except Exception:
            pass

    def get_candles(self, active_id, count, to_ts):
        with self.lock:
            for attempt in range(2):
                if self.status != "connected":
                    self.connect()
                self.reply, self.reply_evt = None, threading.Event()
                self.ws.send(json.dumps({"name": "sendMessage", "request_id": str(int(time.time() * 1000)),
                                         "msg": {"name": "get-candles", "version": "2.0",
                                                 "body": {"active_id": active_id, "split_normalization": True,
                                                          "size": CANDLE_SECONDS, "to": int(to_ts),
                                                          "count": int(count), "": active_id}}}))
                if self.reply_evt.wait(20) and isinstance(self.reply, list):
                    return self.reply
                log("No candle reply, reconnecting...")
                self.status = "disconnected"
                self.close()
            raise RuntimeError("IQ Option did not send candles. Try again in a minute.")


class DemoClient:
    """Fake OTC-like candles (consistent over time) so the app can be tried without logging in."""
    status = "demo data"
    T0 = 1767225600  # 2026-01-01 UTC

    def __init__(self):
        self.series = {}

    def _upto(self, aid, idx):
        s = self.series.setdefault(aid, [])
        p = s[-1][1] if s else 1.0 + aid / 100
        while len(s) <= idx:
            i = len(s)
            rnd = random.Random(aid * 1000003 + i)
            o = p
            p = o + (rnd.random() - 0.5) * 0.0009 + 0.00015 * math.sin(i / 8 + aid)
            s.append((o, p, max(o, p) + rnd.random() * 0.0002, min(o, p) - rnd.random() * 0.0002))
        return s

    def get_candles(self, active_id, count, to_ts):
        end = (int(to_ts) - self.T0) // CANDLE_SECONDS
        s = self._upto(active_id, end)
        out = []
        for i in range(max(0, end - int(count) + 1), end + 1):
            o, c, hi, lo = s[i]
            t = self.T0 + i * CANDLE_SECONDS
            out.append({"from": t, "to": t + CANDLE_SECONDS, "open": o, "close": c, "max": hi, "min": lo})
        return out


class Store:
    """Keeps up to 6000 candles per pair so refreshes only download the newest few."""

    def __init__(self, client):
        self.client = client
        self.data = {}
        self.lock = threading.Lock()

    def candles(self, symbol, size):
        aid = ASSETS[symbol]
        now = time.time()
        with self.lock:
            have = self.data.setdefault(symbol, {})
            fresh = self.client.get_candles(aid, 100 if len(have) >= size else 1000, now)
            for c in fresh:
                have[int(c["from"])] = c
            while len(have) < size:
                oldest = min(have) if have else int(now)
                chunk = self.client.get_candles(aid, 1000, oldest - 1)
                added = 0
                for c in chunk:
                    if int(c["from"]) not in have:
                        have[int(c["from"])] = c
                        added += 1
                if not added:
                    break
            for k in sorted(have)[:-6000]:
                del have[k]
            keys = sorted(have)[-size:]
            rows = []
            for k in reversed(keys):  # newest first, like Twelve Data
                c = have[k]
                hi, lo = c.get("max", c.get("high")), c.get("min", c.get("low"))
                if None in (hi, lo, c.get("open"), c.get("close")):
                    continue
                rows.append({"datetime": datetime.fromtimestamp(k, timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                             "open": c["open"], "high": hi, "low": lo, "close": c["close"]})
            return rows


def make_handler(store):
    class H(BaseHTTPRequestHandler):
        server_version = "PremamuluOTC"
        sys_version = ""

        def log_message(self, fmt, *args):
            pass

        def _send(self, code, body, ctype, cache="no-store"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; script-src 'self' 'unsafe-inline'; worker-src 'self' blob:; "
                             "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
                             "object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj).encode(), "application/json")

        def do_GET(self):
            u = urlparse(self.path)
            host = (self.headers.get("Host") or "").split(":")[0]
            if host not in ("localhost", "127.0.0.1"):  # blocks DNS-rebinding tricks
                return self._send(403, b"forbidden", "text/plain")
            if u.path == "/api/candles":
                q = parse_qs(u.query)
                sym = (q.get("symbol") or [""])[0]
                try:
                    size = max(10, min(5000, int((q.get("outputsize") or ["100"])[0])))
                except ValueError:
                    size = 100
                if sym not in ASSETS:
                    return self._json({"status": "error", "message": "Unknown OTC pair"})
                try:
                    return self._json({"status": "ok", "values": store.candles(sym, size)})
                except Exception as e:  # noqa: BLE001
                    log("Candle error:", str(e)[:160])
                    return self._json({"status": "error", "message": str(e)[:160]})
            if u.path == "/api/status":
                return self._json({"status": getattr(store.client, "status", "?"), "pairs": list(ASSETS)})
            if u.path in STATIC:
                name, ctype = STATIC[u.path]
                p = os.path.join(WEB, name)
                if os.path.exists(p):
                    with open(p, "rb") as f:
                        return self._send(200, f.read(), ctype, "no-cache")
            return self._send(404, b"not found", "text/plain")

    return H


def main():
    cfg = load_config()
    port = int(cfg.get("PORT", "8080"))
    if "--demo-data" in sys.argv:
        client = DemoClient()
        log("DEMO DATA mode: fake candles, no IQ Option login.")
    else:
        try:
            import requests  # noqa: F401
            import websocket  # noqa: F401
        except ImportError:
            print("Missing packages. Run:  pip install websocket-client requests")
            sys.exit(1)
        email = cfg.get("IQ_EMAIL") or input("IQ Option DEMO account email: ").strip()
        password = cfg.get("IQ_PASSWORD") or getpass.getpass("Password (hidden, not saved): ")
        client = IQClient(email, password)
        try:
            client.connect()
        except Exception as e:  # noqa: BLE001
            print("Could not connect:", e)
            sys.exit(1)
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(Store(client)))
    log(f"Premamulu OTC is running. Open  http://localhost:{port}  in Chrome on this phone.")
    log("Keep Termux open. Press Ctrl+C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        log("Stopped.")


if __name__ == "__main__":
    main()
