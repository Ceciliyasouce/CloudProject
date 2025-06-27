from flask import Flask, request, render_template
import numpy as np
from azure.storage.blob import BlobServiceClient
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

# Global variables to cache the model and columns
lr_model = None
feature_columns = None

def load_model_and_columns():
    """Load model and feature columns once and cache them globally"""
    global lr_model, feature_columns
    
    if lr_model is not None and feature_columns is not None:
        return lr_model, feature_columns
    
    connection_string = os.getenv('CONNECTION_STRING')
    container_name = os.getenv('CONTAINER_NAME')
    
    if not connection_string or not container_name:
        raise ValueError("CONNECTION_STRING or CONTAINER_NAME not found in environment variables")
    
    # Connect to Azure Blob Storage
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    
    # Load the model
    try:
        model_blob_name = "models/linear_model.pkl"
        model_blob_client = blob_service_client.get_blob_client(container=container_name, blob=model_blob_name)
        
        # Download model data as bytes and load directly
        model_download_stream = model_blob_client.download_blob()
        model_bytes = model_download_stream.readall()  # Read once and store
        
        # Load model from bytes
        model_buffer = BytesIO(model_bytes)
        lr_model = cloudpickle.load(model_buffer)
        print("Model loaded successfully")
        
    except Exception as e:
        print(f"Error loading model: {str(e)}")
        raise
    
    # Load feature columns
    try:
        columns_blob_name = "models/X_columns.json"
        columns_blob_client = blob_service_client.get_blob_client(container=container_name, blob=columns_blob_name)
        
        # Download columns data as bytes and parse
        columns_download_stream = columns_blob_client.download_blob()
        columns_bytes = columns_download_stream.readall()  # Read once and store
        
        # Parse JSON
        json_str = columns_bytes.decode('utf-8')
        feature_columns = json.loads(json_str)
        print("Feature columns loaded successfully")
        
    except Exception as e:
        print(f"Error loading feature columns: {str(e)}")
        raise
    
    return lr_model, feature_columns

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    try:
        # Access form inputs from the HTML
        location = request.form.get('location')
        sqft = request.form.get('sqft')
        bath = request.form.get('bath')
        size = request.form.get('size')

        # Validate inputs
        if not all([location, sqft, bath, size]):
            return "Error: All fields are required", 400

        # Convert numeric inputs
        try:
            sqft = float(sqft)
            bath = int(bath)
            size = int(size)
        except ValueError:
            return "Error: Invalid numeric input", 400

        # Store in a dictionary
        form_data = {
            'location': location,
            'sqft': sqft,
            'bath': bath,
            'size': size
        }

        print("Received form data:", form_data)
        
        # Get prediction
        prediction = predict_price(form_data)
        
        return render_template('output.html', 
                             location=form_data['location'],
                             sqft=form_data['sqft'],
                             bath=form_data['bath'],
                             size=form_data['size'],
                             ans=int(prediction))
                             
    except Exception as e:
        print(f"Error in submit route: {str(e)}")
        return f"Error processing request: {str(e)}", 500

def predict_price(form_data):
    """Make prediction using cached model and columns"""
    try:
        # Load model and columns (cached after first load)
        model, columns = load_model_and_columns()
        
        # Extract input values
        location = form_data['location']
        sqft = form_data['sqft']
        bath = form_data['bath']
        bhk = form_data['size']
        
        # Convert columns to numpy array for easier searching
        columns_array = np.array(columns)
        
        # Find location index
        loc_indices = np.where(columns_array == location)[0]
        
        # Create feature vector
        x = np.zeros(len(columns))
        x[0] = sqft
        x[1] = bath
        x[2] = bhk
        
        # Set location feature if found
        if len(loc_indices) > 0:
            x[loc_indices[0]] = 1
        
        # Make prediction
        prediction = model.predict([x])[0]
        
        print(f"Prediction for {form_data}: {prediction}")
        return prediction
        
    except Exception as e:
        print(f"Error in predict_price: {str(e)}")
        raise

@app.errorhandler(500)
def internal_error(error):
    return "Internal server error occurred", 500

@app.errorhandler(404)
def not_found(error):
    return "Page not found", 404

if __name__ == '__main__':
    try:
        # Pre-load model and columns on startup
        load_model_and_columns()
        print("Model and columns pre-loaded successfully")
    except Exception as e:
        print(f"Warning: Could not pre-load model: {str(e)}")
    
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8000)), debug=False)
