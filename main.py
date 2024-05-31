import json
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, CCIIndicator
from ta.volatility import BollingerBands, bollinger_mavg
from websocket import WebSocketApp
from datetime import datetime, timedelta, timezone
from binance.client import Client
import pandas as pd
import joblib


#region definitions
SOCKET = 'wss://stream.binance.com:9443/ws/btcusdt@kline_1m'

SHORT_RSI_PERIOD = 14
MIDDLE_RSI_PERIOD = 28
LONG_RSI_PERIOD = 42

SHORT_EMA_PERIOD = 13
LONG_EMA_PERIOD = 50
TRADE_QUANTITY = 0.01
temp_data = []


#endregion

#region BinanceApı || Alsu used for data creater

client = Client()

# Şu anki zamanı al
end_time = datetime.now(timezone.utc)
# Kaç dakika geriye gitmek istediğinizi belirleyin (örneğin 60 dakika)
minutes_back = 3150
start_time = end_time - timedelta(minutes=minutes_back)

# Zaman formatını string'e çevir (Binance API için)
start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")

# Dakika bazında BTC/USDT verilerini al
klines = client.get_historical_klines("BTCUSDT", Client.KLINE_INTERVAL_15MINUTE, start_str, end_str)

# Veriyi DataFrame'e çevir
df = pd.DataFrame(klines, columns=[
    'timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades',
    'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
])

# Zaman damgasını datetime formatına çevir
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

columns_to_keep = [ 'open', 'high', 'low', 'close', 'volume']
df = df[columns_to_keep]
column_mapping = {
    'open': 'Open',
    'high': 'High',
    'low': 'Low',
    'close': 'Close',
    'volume': 'Volume'
}
df = df.rename(columns=column_mapping)

closes_df = pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume'])
closes_df = pd.concat([closes_df, df], ignore_index=True)
# closes_df.to_excel("new_veri_15min.xlsx")
#closes_df.to_excel("binance_result_15min.xlsx")

data_df = closes_df.iloc[-201:]




#endregion

#region findIndicator
def calculate_RSI(period,dataToIndex):
    if len(dataToIndex) >= period:
        rsi = RSIIndicator(dataToIndex['Close'], period)
        rsi_values = rsi.rsi()
        return rsi_values[len(rsi_values)-1]

def calculate_EMA(period,dataToIndex):
    if len(dataToIndex) > period:
        EMA = EMAIndicator(dataToIndex['Close'],period)
        EMA_values = EMA.ema_indicator()
        return EMA_values[len(EMA_values)- 1]

def calculate_CCIIndicator(dataToIndex,window):
    if len(dataToIndex) > window:

        CCI_Value=CCIIndicator(high=dataToIndex["High"],low=dataToIndex["Low"],close=dataToIndex['Close'],window=window)
        result = CCI_Value.cci()
        return result[len(result)- 1]

def calculate_MAIndicator(window,dataToIndex):
    if len(dataToIndex) > window:
        ma_value = bollinger_mavg(dataToIndex['Close'],window=window)
        result = ma_value[len(ma_value) - 1]
        return result

#endregion

#region addModel
high_model = joblib.load('high_price_15min.joblib')
low_model = joblib.load('low_price_15min.joblib')
print("Model başarıyla yüklendi.")

#endregion

#region prediction

def is_a_signal(price,high_prediction,low_prediction):
    if high_prediction > low_prediction and price < high_prediction and price > low_prediction:
        profitRatio = (high_prediction - price) / price
        lossRatio = (price - low_prediction) / price
        if(profitRatio > lossRatio):
            return True
    return False
    # if high_prediction > low_prediction and price < high_prediction and price > low_prediction:
    #     profitRatio = (high_prediction - price)/price
    #     lossRatio = (price - low_prediction)/price
    #     if profitRatio > 0.01 and lossRatio < 0.005:
    #         return True
    # return False


predictions = pd.DataFrame()
high_prediction = 0
low_prediction = 0
def predict_values(candle,last_closes_df):
    global predictions
    new_value_df = {
        'Open': last_closes_df['Open'].astype(float).tolist(),
        'Close': last_closes_df['Close'].astype(float).tolist(),
        'High': last_closes_df['High'].astype(float).tolist(),
        'Low': last_closes_df['Low'].astype(float).tolist(),
        'Volume': last_closes_df['Volume'].astype(float).tolist()
    }
    df = pd.DataFrame(new_value_df)
    short_rsi = calculate_RSI(SHORT_RSI_PERIOD, df)
    middle_rsi = calculate_RSI(MIDDLE_RSI_PERIOD, df)
    long_rsi = calculate_RSI(LONG_RSI_PERIOD, df)
    short_EMA = calculate_EMA(SHORT_EMA_PERIOD, df)
    long_EMA = calculate_EMA(LONG_EMA_PERIOD, df)
    CCI = calculate_CCIIndicator(df, 50)
    slow_MA = calculate_MAIndicator(50, df)
    middle_MA = calculate_MAIndicator(100, df)
    long_MA = calculate_MAIndicator(200, df)
    result = ({
        'Datetime': datetime.fromtimestamp(candle['t'] / 1000),
        "short_rsi": short_rsi,
        "middle_rsi": middle_rsi,
        "long_rsi": long_rsi,
        "short_EMA": short_EMA,
        "long_EMA": long_EMA,
        "CCI": CCI,
        "slow_MA": slow_MA,
        "middle_MA": middle_MA,
        "long_MA": long_MA,
        "Open": float(candle["o"]),
        "Close": float(candle["c"]),
        "High": float(candle["h"]),
        "Low": float(candle["l"]),
        'Volume': float(candle["v"])
    })
    print(result)
    prediction_Data = [[short_rsi, middle_rsi, long_rsi, short_EMA, long_EMA, CCI, slow_MA, middle_MA, long_MA, float(candle["c"])]]
    high_prediction = (high_model.predict(prediction_Data))
    high_prediction = high_prediction[0]
    low_prediction = (low_model.predict(prediction_Data))
    low_prediction = low_prediction[0]
    result["High_Prediction"] = high_prediction
    result["Low_Prediction"] = low_prediction

    print("current price ", float(candle["c"]))
    print("high Prediction:", high_prediction)
    print("low Prediction:", low_prediction)

    predictions = predictions._append(result, ignore_index=True)
    predictions.to_excel('predictions.xlsx', index=False)
    predictions.to_excel("C:\\Users\\Pixel\\PycharmProjects\\telegramsender\\predictions.xlsx", index=False)

    # if signalCheck:
    #     predictions = predictions._append(result, ignore_index=True)
    #     predictions.to_excel('predictions.xlsx', index=False)

#endregion


data_df.to_excel("first_200_candle_info.xlsx")
def on_message(ws, message):
    json_message= json.loads(message)
    candle = json_message['k']
    is_candle_closed = candle['x']
    current_time = datetime.fromtimestamp(candle['t'] / 1000)

    global data_df,predictions

    if is_candle_closed and current_time.minute % 15 == 0:
        closed_values = {
         'Datetime':  datetime.fromtimestamp(candle['t'] / 1000),
         'Open': float(candle["o"]),
         'Close': float(candle["c"]),
         'High': float(candle["h"]),
         'Low': float(candle["l"]),
         'Volume': float(candle["v"])
        }
        temp_df = data_df.copy()
        temp_df = temp_df._append(closed_values,ignore_index=True)
        temp_df = temp_df.reset_index(drop=True)
        predict_values(candle,temp_df)

        data_df = data_df._append(closed_values, ignore_index=True).reset_index(drop=True)
        data_df.to_excel("updated_candle_info.xlsx",index=False)

        print("Updated data_df with the latest 15m kline data:")

    # if is_candle_closed and high_prediction != 0 and low_prediction != 0:
    #     signalCheck = is_a_signal(float(candle["c"]), high_prediction, low_prediction)
    #     if signalCheck:
    #         newPredicate = {
    #             'High' : high_prediction,
    #             'Low' : low_prediction,
    #             'Current' : float(candle["c"])
    #         }
    #         predictions = predictions._append(newPredicate, ignore_index=True)
    #         predictions.to_excel('predictions.xlsx', index=False)
    #         print("new prediction saved")

def on_close(ws):
    print("close connection")

def on_open(ws):
    print("opened connection")

ws = WebSocketApp(SOCKET,on_open=on_open,on_close=on_close,on_message=on_message)

ws.run_forever()




