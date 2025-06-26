from flask import Flask, request, render_template
import numpy as np
from azure.storage.blob import BlobServiceClient
#import joblib
from io import BytesIO
import pandas as pd
import cloudpickle
import json
import os
from dotenv import load_dotenv

import sys

# Also, sometimes patch _new_Index as an attribute
setattr(pd.Index, '_new_Index', pd.Index)
load_dotenv()


app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    # Access form inputs from the HTML
    location = request.form.get('location')
    sqft = request.form.get('sqft')
    bath = request.form.get('bath')
    size = request.form.get('size')

    # Store in a dictionary or use as needed
    form_data = {
        'location': location,
        'sqft': sqft,
        'bath': bath,
        'size': size
    }

    # For now, just print or return
    print("Received form data:", form_data)
    ans = user_input(form_data)
    return render_template('output.html', 
                                 location=form_data['location'],
                                 sqft=form_data['sqft'],
                                 bath=form_data['bath'],
                                 size=form_data['size'],
                                 ans=int(ans))
    #return f"Received: {form_data}: {ans}"


#def predict_price(location,sqft,bath,bhk):
    

def user_input(form_data):
    connection_string =  os.getenv('connection_string')
    container_name = os.getenv('container_name')
    blob_name = "models/linear_model.pkl"
    local_file_path = "linear_model.pkl"

    sys.modules['pandas.core.indexes.base'] = pd.Index
    sys.modules['pandas.core.indexes.base.Index'] = pd.Index

    # Step 1: Connect to Azure Blob and download model
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

    # Download blob to local file
    with open(local_file_path, "wb") as f:
        download_stream = blob_client.download_blob()
        f.write(download_stream.readall())
    print(f"Model downloaded and saved to {local_file_path}")

    with open(local_file_path, "rb") as f:
        lr = cloudpickle.load(f)


    blob_name2 = "models/X_columns.json"
    local_file_path2 = "X_columns.json"
    blob_client2 = blob_service_client.get_blob_client(container=container_name, blob=blob_name2)
    # Download blob content as bytes
    download_stream = blob_client2.download_blob()
    json_bytes = download_stream.readall()

    # Decode bytes to string
    json_str = json_bytes.decode('utf-8')

    # Parse JSON string to Python list
    fcolumns = json.loads(json_str)

    # # Step 2: Download model into memory
    # download_stream2 = blob_client2.download_blob()
    # model_bytes2 = BytesIO(download_stream2.readall())
    # # sample_input = pd.DataFrame({
    # # 'location': ["1st Phase JP Nagar"],
    # # 'sqft': [1500],
    # # 'bath': [2],
    # # 'size': [3],
    # #   # Assuming location is encoded
    # # })

    # # # Step 5: Make prediction
    # # prediction = lr.predict(sample_input)
    # # return prediction
    # #Step 3: Load model
    # X = joblib.load(model_bytes2)

    location = form_data['location']
    sqft = form_data['sqft']
    bath = form_data['bath']
    bhk = form_data['size']

    #feature_columns = X.columns  # if X is a DataFrame

    loc_index=np.where(fcolumns==location)[0]
    x=np.zeros(len(fcolumns))
    x[0]=sqft
    x[1]=bath
    x[2]=bhk
    if loc_index>=0:
        x[loc_index]=1
    return lr.predict([x])[0]

if __name__ == '__main__':
    app.run(debug=True)
