
import requests
import time
import datetime
import json
import telebot
import threading

TOKEN = "7641431148:AAHIHIJkiVep9H7iJqchVZn9estuHq94CA0"
bot = telebot.TeleBot(TOKEN)
CHAT_ID = None

POSITION_FILE = "position.json"
LOG_FILE = "neiro_log.json"

def get_prices():
    neiro_data = requests.get("https://api.binance.com/api/v3/ticker/24hr?symbol=NEIROTRY").json()
    btc_data = requests.get("https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT").json()
    neiro_depth = requests.get("https://api.binance.com/api/v3/depth?symbol=NEIROTRY&limit=50").json()
    btc_depth = requests.get("https://api.binance.com/api/v3/depth?symbol=BTCUSDT&limit=50").json()

    def calc_ratio(depth):
        total_bids = sum(float(b[1]) for b in depth["bids"])
        total_asks = sum(float(a[1]) for a in depth["asks"])
        total = total_bids + total_asks
        buy_pct = (total_bids / total) * 100 if total else 0
        sell_pct = 100 - buy_pct
        return round(buy_pct), round(sell_pct)

    neiro_ratio = calc_ratio(neiro_depth)
    btc_ratio = calc_ratio(btc_depth)

    return {
        "neiro_price": float(neiro_data["lastPrice"]),
        "neiro_change": float(neiro_data["priceChangePercent"]),
        "btc_price": float(btc_data["lastPrice"]),
        "btc_change": float(btc_data["priceChangePercent"]),
        "neiro_buy": neiro_ratio[0],
        "neiro_sell": neiro_ratio[1],
        "btc_buy": btc_ratio[0],
        "btc_sell": btc_ratio[1]
    }

def get_klines(symbol, interval="15m", limit=50):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    return requests.get(url).json()

def calc_rsi(prices):
    gains = []
    losses = []
    for i in range(1, len(prices)):
        delta = prices[i] - prices[i-1]
        if delta > 0:
            gains.append(delta)
        else:
            losses.append(abs(delta))
    avg_gain = sum(gains[-14:]) / 14 if gains else 1
    avg_loss = sum(losses[-14:]) / 14 if losses else 1
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def analyze_technical():
    klines = get_klines("NEIROTRY", "15m", 50)
    closes = [float(k[4]) for k in klines]
    volumes = [float(k[5]) for k in klines]

    ema20 = sum(closes[-20:]) / 20
    ema50 = sum(closes[-50:]) / 50
    rsi = calc_rsi(closes)
    macd = sum(closes[-12:]) / 12 - sum(closes[-26:]) / 26
    signal = macd
    histogram = macd - signal
    vol_avg = sum(volumes) / len(volumes)
    vol_boost = volumes[-1] > vol_avg * 1.3

    btc_klines = get_klines("BTCUSDT", "15m", 3)
    btc_closes = [float(k[4]) for k in btc_klines]
    btc_down = btc_closes[-1] < btc_closes[-2]

    # Günlük hedef hesaplama
    hedef_fiyat = round(closes[-1] * 1.05, 6)  # %5 yukarı

    buy = (
        ema20 > ema50 and
        rsi > 35 and rsi < 60 and
        macd > signal and
        histogram > 0 and
        vol_boost and
        btc_down
    )

    return {
        "rsi": round(rsi, 2),
        "ema20": round(ema20, 6),
        "ema50": round(ema50, 6),
        "macd": round(macd, 6),
        "signal": round(signal, 6),
        "histogram": round(histogram, 6),
        "vol_boost": vol_boost,
        "btc_down": btc_down,
        "buy_signal": buy,
        "hedef": hedef_fiyat
    }

def load_position():
    try:
        with open(POSITION_FILE, "r") as f:
            return json.load(f)
    except:
        return {"active": False, "entry": 0.0}

def save_position(entry):
    with open(POSITION_FILE, "w") as f:
        json.dump({"active": True, "entry": entry}, f)

def clear_position():
    with open(POSITION_FILE, "w") as f:
        json.dump({"active": False, "entry": 0.0}, f)

def log_trade(entry, exit_price, pnl, pnl_pct):
    try:
        with open(LOG_FILE, "r") as f:
            data = json.load(f)
    except:
        data = []
    data.append({
        "time": datetime.datetime.now().isoformat(),
        "entry": entry,
        "exit": exit_price,
        "pnl": pnl,
        "pnl_percent": pnl_pct
    })
    with open(LOG_FILE, "w") as f:
        json.dump(data, f, indent=2)

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    global CHAT_ID
    CHAT_ID = message.chat.id
    text = message.text.lower()

    if text == "sinyal":
        prices = get_prices()
        tech = analyze_technical()
        pos = load_position()

        msg = f"📊 **FİYAT BİLGİLERİ**\nNEIRO: {prices['neiro_price']} ₺ (%{prices['neiro_change']}) | BTC: {prices['btc_price']}$ (%{prices['btc_change']})\n"               f"Günlük hedef: {tech['hedef']} ₺\nNEIRO alış/satış: %{prices['neiro_buy']} / %{prices['neiro_sell']}\nBTC alış/satış: %{prices['btc_buy']} / %{prices['btc_sell']}\n"               f"\n📈 **TEKNİK GÖSTERGELER**\nRSI (Göreceli Güç): {tech['rsi']} → 50'nin altı = alım gücü düşük\n"               f"EMA20: {tech['ema20']} | EMA50: {tech['ema50']} → Trend {'yukarı' if tech['ema20'] > tech['ema50'] else 'aşağı'}\n"               f"MACD Histogram: {tech['histogram']} → {'Pozitif' if tech['histogram'] > 0 else 'Negatif'}\n"               f"Hacim: {'Yüksek' if tech['vol_boost'] else 'Normal'}\nBTC düşüşte mi? {'Evet' if tech['btc_down'] else 'Hayır'}\n"               f"\n🧠 **GENEL SİNYAL:** {'📈 AL' if tech['buy_signal'] else '⏳ Bekle'}"

        if pos["active"]:
            current = prices["neiro_price"]
            change = (current - pos["entry"]) / pos["entry"] * 100
            msg += f"\n\n📥 Pozisyon: Giriş: {pos['entry']} ₺ | Anlık: {current} ₺ | K/Z: {change:.2f}%"

        bot.send_message(CHAT_ID, msg)

threading.Thread(target=bot.polling).start()
#

