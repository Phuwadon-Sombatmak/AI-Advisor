import numpy as np
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
from sklearn.preprocessing import MinMaxScaler

def predict_next_price(prices):

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