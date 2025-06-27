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
import traceback

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
    
    print("=== Starting load_model_and_columns ===")
    
    if lr_model is not None and feature_columns is not None:
        print("Model and columns already cached, returning cached version")
        return lr_model, feature_columns
    
    connection_string = os.getenv('CONNECTION_STRING')
    container_name = os.getenv('CONTAINER_NAME')
    
    print(f"CONNECTION_STRING exists: {bool(connection_string)}")
    print(f"CONTAINER_NAME: {container_name}")
    
    if not connection_string or not container_name:
        raise ValueError("CONNECTION_STRING or CONTAINER_NAME not found in environment variables")
    
    try:
        # Connect to Azure Blob Storage
        print("Creating BlobServiceClient...")
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        print("BlobServiceClient created successfully")
        
        # Load the model
        print("=== Loading Model ===")
        model_blob_name = "models/linear_model.pkl"
        print(f"Getting blob client for: {model_blob_name}")
        model_blob_client = blob_service_client.get_blob_client(container=container_name, blob=model_blob_name)
        
        print("Starting model download...")
        model_download_stream = model_blob_client.download_blob()
        print("Model download stream created")
        
        print("Reading model bytes...")
        model_bytes = model_download_stream.readall()
        print(f"Model bytes read successfully, size: {len(model_bytes)} bytes")
        
        print("Loading model with cloudpickle...")
        model_buffer = BytesIO(model_bytes)
        lr_model = cloudpickle.load(model_buffer)
        print("Model loaded successfully")
        
        # Load feature columns
        print("=== Loading Feature Columns ===")
        columns_blob_name = "models/X_columns.json"
        print(f"Getting blob client for: {columns_blob_name}")
        columns_blob_client = blob_service_client.get_blob_client(container=container_name, blob=columns_blob_name)
        
        print("Starting columns download...")
        columns_download_stream = columns_blob_client.download_blob()
        print("Columns download stream created")
        
        print("Reading columns bytes...")
        columns_bytes = columns_download_stream.readall()
        print(f"Columns bytes read successfully, size: {len(columns_bytes)} bytes")
        
        print("Parsing JSON...")
        json_str = columns_bytes.decode('utf-8')
        feature_columns = json.loads(json_str)
        print(f"Feature columns loaded successfully, count: {len(feature_columns)}")
        
        print("=== load_model_and_columns completed successfully ===")
        return lr_model, feature_columns
        
    except Exception as e:
        print(f"ERROR in load_model_and_columns: {str(e)}")
        print(f"ERROR type: {type(e)}")
        print("Full traceback:")
        traceback.print_exc()
        raise

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    print("=== Submit route called ===")
    try:
        # Access form inputs from the HTML
        location = request.form.get('location')
        sqft = request.form.get('sqft')
        bath = request.form.get('bath')
        size = request.form.get('size')
        
        print(f"Form data received: location={location}, sqft={sqft}, bath={bath}, size={size}")

        # Validate inputs
        if not all([location, sqft, bath, size]):
            print("ERROR: Missing form fields")
            return "Error: All fields are required", 400

        # Convert numeric inputs
        try:
            sqft = float(sqft)
            bath = int(bath)
            size = int(size)
            print(f"Converted values: sqft={sqft}, bath={bath}, size={size}")
        except ValueError as e:
            print(f"ERROR converting numeric inputs: {str(e)}")
            return "Error: Invalid numeric input", 400

        # Store in a dictionary
        form_data = {
            'location': location,
            'sqft': sqft,
            'bath': bath,
            'size': size
        }

        print("Calling predict_price...")
        
        # Get prediction
        prediction = predict_price(form_data)
        print(f"Prediction received: {prediction}")
        
        return render_template('output.html', 
                             location=form_data['location'],
                             sqft=form_data['sqft'],
                             bath=form_data['bath'],
                             size=form_data['size'],
                             ans=int(prediction))
                             
    except Exception as e:
        print(f"ERROR in submit route: {str(e)}")
        print(f"ERROR type: {type(e)}")
        print("Full traceback:")
        traceback.print_exc()
        return f"Error processing request: {str(e)}", 500

def predict_price(form_data):
    """Make prediction using cached model and columns"""
    print("=== predict_price called ===")
    try:
        print("Loading model and columns...")
        # Load model and columns (cached after first load)
        model, columns = load_model_and_columns()
        print("Model and columns loaded successfully")
        
        # Extract input values
        location = form_data['location']
        sqft = form_data['sqft']
        bath = form_data['bath']
        bhk = form_data['size']
        
        print(f"Input values: location={location}, sqft={sqft}, bath={bath}, bhk={bhk}")
        
        # Convert columns to numpy array for easier searching
        print("Converting columns to numpy array...")
        columns_array = np.array(columns)
        print(f"Columns array shape: {columns_array.shape}")
        
        # Find location index
        print(f"Looking for location '{location}' in columns...")
        loc_indices = np.where(columns_array == location)[0]
        print(f"Location indices found: {loc_indices}")
        
        # Create feature vector
        print("Creating feature vector...")
        x = np.zeros(len(columns))
        x[0] = sqft
        x[1] = bath
        x[2] = bhk
        
        # Set location feature if found
        if len(loc_indices) > 0:
            x[loc_indices[0]] = 1
            print(f"Set location feature at index {loc_indices[0]}")
        else:
            print("Location not found in columns")
        
        print(f"Feature vector: {x[:10]}...")  # Show first 10 elements
        
        # Make prediction
        print("Making prediction...")
        prediction = model.predict([x])[0]
        
        print(f"Prediction completed: {prediction}")
        return prediction
        
    except Exception as e:
        print(f"ERROR in predict_price: {str(e)}")
        print(f"ERROR type: {type(e)}")
        print("Full traceback:")
        traceback.print_exc()
        raise

@app.errorhandler(500)
def internal_error(error):
    print(f"500 error handler called: {error}")
    return "Internal server error occurred", 500

@app.errorhandler(404)
def not_found(error):
    print(f"404 error handler called: {error}")
    return "Page not found", 404

if __name__ == '__main__':
    print("=== Flask App Starting ===")
    try:
        # Pre-load model and columns on startup
        print("Pre-loading model and columns...")
        load_model_and_columns()
        print("Model and columns pre-loaded successfully")
    except Exception as e:
        print(f"Warning: Could not pre-load model: {str(e)}")
        print("Full traceback:")
        traceback.print_exc()
    
    print("Starting Flask server...")
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)
