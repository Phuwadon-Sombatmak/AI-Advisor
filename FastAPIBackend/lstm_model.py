import numpy as np
from sklearn.preprocessing import MinMaxScaler


def _load_tensorflow_layers():
    try:
        from tensorflow.keras.layers import LSTM, Dense
        from tensorflow.keras.models import Sequential
    except ImportError as exc:
        raise RuntimeError(
            "TensorFlow is required for the LSTM forecasting module. "
            "Install optional ML dependencies with "
            "`python -m pip install -r FastAPIBackend/requirements-ml.txt`."
        ) from exc
    return Sequential, LSTM, Dense

def predict_next_price(prices):
    Sequential, LSTM, Dense = _load_tensorflow_layers()

    scaler = MinMaxScaler()
    data = scaler.fit_transform(np.array(prices).reshape(-1,1))

    X=[]
    y=[]

    window=20

    for i in range(len(data)-window):
        X.append(data[i:i+window])
        y.append(data[i+window])

    X=np.array(X)
    y=np.array(y)

    model = Sequential()
    model.add(LSTM(50,input_shape=(window,1)))
    model.add(Dense(1))

    model.compile(loss="mse",optimizer="adam")

    model.fit(X,y,epochs=5,batch_size=8,verbose=0)

    last=data[-window:]
    last=last.reshape(1,window,1)

    pred=model.predict(last)

    return float(scaler.inverse_transform(pred)[0][0])
