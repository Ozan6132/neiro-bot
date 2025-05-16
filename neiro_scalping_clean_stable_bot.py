
import requests
import json
import telebot
import datetime

TOKEN = "7641431148:AAEmlLxKn6lSFeZcaUvbhQw6zUkphfSDVq4"
bot = telebot.TeleBot(TOKEN)
CHAT_ID = None

POSITION_FILE = "position.json"
LOG_FILE = "neiro_log.json"

def get_prices():
    neiro_data = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=neiro&vs_currencies=try").json()
    btc_data = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd").json()

    return {
        "neiro_price": float(neiro_data["neiro"]["try"]),
        "neiro_change": 0.0,
        "btc_price": float(btc_data["bitcoin"]["usd"])
    }

def get_klines(symbol="NEIROTRY", interval="15m", limit=50):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    return requests.get(url).json()

def calc_rsi(prices):
    gains = []
    losses = []
    for i in range(1, len(prices)):
        delta = prices[i] - prices[i - 1]
        if delta >= 0:
            gains.append(delta)
        else:
            losses.append(-delta)
    avg_gain = sum(gains[-14:]) / 14 if gains else 1
    avg_loss = sum(losses[-14:]) / 14 if losses else 1
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def analyze_technical():
    klines = get_klines()
    closes = [float(k[4]) for k in klines]
    volumes = [float(k[5]) for k in klines]
    ema20 = sum(closes[-20:]) / 20
    ema50 = sum(closes[-50:]) / 50
    rsi = calc_rsi(closes)
    vol_avg = sum(volumes) / len(volumes)
    vol_boost = volumes[-1] > vol_avg * 1.2
    hedef = round(closes[-1] * 1.05, 6)
    buy = ema20 > ema50 and 40 < rsi < 60 and vol_boost
    return {
        "rsi": rsi,
        "ema20": ema20,
        "ema50": ema50,
        "vol_boost": vol_boost,
        "buy_signal": buy,
        "hedef": hedef
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

        msg = f"📊 NEIRO: {prices['neiro_price']} ₺ (%{prices['neiro_change']})\n"               f"BTC: {prices['btc_price']} $ (%{prices['btc_change']})\n"               f"Günlük Hedef: {tech['hedef']} ₺\n"               f"RSI: {tech['rsi']} | EMA20: {tech['ema20']:.6f} | EMA50: {tech['ema50']:.6f}\n"               f"Hacim: {'Yüksek' if tech['vol_boost'] else 'Normal'}\n"               f"Sinyal: {'📈 AL' if tech['buy_signal'] else '⏳ BEKLE'}"

        if pos["active"]:
            current = prices["neiro_price"]
            change = (current - pos["entry"]) / pos["entry"] * 100
            msg += f"\n\n📥 Pozisyon: Giriş: {pos['entry']} ₺ | Şu an: {current} ₺ | K/Z: {change:.2f}%"

        bot.send_message(CHAT_ID, msg)

    elif text.startswith("giriş"):
        try:
            entry = float(text.split()[1])
            save_position(entry)
            bot.send_message(CHAT_ID, f"🎯 Giriş kaydedildi: {entry} ₺")
        except:
            bot.send_message(CHAT_ID, "⚠️ Giriş komutu hatalı. Örnek: giriş 0.00052")

    elif text == "pozisyon":
        pos = load_position()
        if not pos["active"]:
            bot.send_message(CHAT_ID, "📭 Aktif pozisyonun yok.")
        else:
            current = get_prices()["neiro_price"]
            change = (current - pos["entry"]) / pos["entry"] * 100
            bot.send_message(CHAT_ID, f"📊 Anlık: {current} ₺ | Giriş: {pos['entry']} ₺ | K/Z: {change:.2f}%")

    elif text == "çık":
        pos = load_position()
        if not pos["active"]:
            bot.send_message(CHAT_ID, "⚠️ Açık pozisyon bulunamadı.")
        else:
            current = get_prices()["neiro_price"]
            pnl = current - pos["entry"]
            pnl_pct = (pnl / pos["entry"]) * 100
            log_trade(pos["entry"], current, pnl, pnl_pct)
            clear_position()
            bot.send_message(CHAT_ID, f"📉 Pozisyon kapatıldı. Çıkış: {current} ₺ | K/Z: {pnl_pct:.2f}%")

if __name__ == "__main__":
    bot.polling()
