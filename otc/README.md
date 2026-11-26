# Premamulu OTC (separate app for IQ Option OTC pairs)

This is a completely separate app from Premamulu, with its own server, page, name, icon, settings and trade log.
It reads **OTC candles from your IQ Option demo account** and runs the same analysis as Premamulu: indicators, 32 candle patterns, 15m/1h trend, the AI models and the proven-history checks. It then gives CALL/PUT signals for **2, 3 or 5 minutes** (OTC maximum), using 1-minute candles.

Pairs: **EUR/USD-OTC, GBP/USD-OTC, USD/JPY-OTC, EUR/JPY-OTC**.

## How it works
`server.py` runs inside **Termux** on your phone. It logs in to IQ Option, downloads the 1-minute OTC candles, and shows the app at **http://localhost:8080** in Chrome on the same phone. Nothing runs on GitHub.

* **Read-only.** The server has no code that can place trades. It only downloads candles.
* **Your password** is typed in Termux and sent only to IQ Option over HTTPS with certificate checking. It is not saved unless you create `config.env` yourself, and that file is never uploaded.
* **Only this phone can open the app.** The server only accepts connections from this phone (`127.0.0.1`).

## One-time setup (Termux)
1. Install **Termux from F-Droid** (the Play Store version is outdated).
2. In Termux, run these lines one by one:
   ```
   pkg update -y && pkg install -y python git
   pip install websocket-client requests
   git clone https://github.com/premkumarsmart5-hub/PAP99.git
   ```
3. In Android settings, set **Termux → Battery → Unrestricted** so Android doesn't stop it in the background.

## Every time you trade
```
cd ~/PAP99/otc
bash start.sh
```
Type your **demo account** email and password. The password is hidden while you type. When you see `Premamulu OTC is running`, open Chrome and go to **http://localhost:8080**. The first time, use **⋮ → Install app** to add the "Premamulu OTC" icon. Keep Termux running in the background. To stop, go back to Termux and press **Ctrl+C**.

To try the app without logging in (fake candles): `bash start.sh --demo-data`

## Updating
```
cd ~/PAP99 && git pull
```

## Notes and risks
* **Automated access:** IQ Option does not officially allow automated access. Use the **demo account only**. Turn off 2-step verification on that demo login, or the server cannot log in.
* **OTC prices:** IQ Option generates OTC prices itself; they are not the real market. Trust only signals marked **VALIDATED**, and check the win rates with **Find best expiry**.
* **Untested on a live account:** this was tested with fake candles only. The live IQ Option connection has not been tried yet. If Termux shows an error, send a screenshot.
