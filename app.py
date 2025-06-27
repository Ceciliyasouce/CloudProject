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
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Patch for pandas compatibility
setattr(pd.Index, '_new_Index', pd.Index)
sys.modules['pandas.core.indexes.base'] = pd.Index
sys.modules['pandas.core.indexes.base.Index'] = pd.Index

load_dotenv()

app = Flask(__name__)

# Global variables to cache the model and columns
lr_model = None
feature_columns = None
blob_service_client = None

def get_blob_service_client():
    """Get or create blob service client"""
    global blob_service_client
    
    if blob_service_client is None:
        connection_string = os.getenv('CONNECTION_STRING')
        if not connection_string:
            raise ValueError("CONNECTION_STRING not found in environment variables")
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        logger.info("BlobServiceClient created")
    
    return blob_service_client

def download_blob_content(container_name, blob_name):
    """Download blob content using the most reliable method"""
    try:
        client = get_blob_service_client()
        blob_client = client.get_blob_client(container=container_name, blob=blob_name)
        
        # Method 1: Try content_as_bytes() - most reliable
        try:
            logger.info(f"Downloading {blob_name} using content_as_bytes()")
            blob_data = blob_client.download_blob().content_as_bytes()
            logger.info(f"Successfully downloaded {blob_name} ({len(blob_data)} bytes)")
            return blob_data
        except Exception as e:
            logger.warning(f"content_as_bytes() failed for {blob_name}: {str(e)}")
            
        # Method 2: Fallback to readall()
        try:
            logger.info(f"Downloading {blob_name} using readall() fallback")
            download_stream = blob_client.download_blob()
            blob_data = download_stream.readall()
            logger.info(f"Successfully downloaded {blob_name} with fallback ({len(blob_data)} bytes)")
            return blob_data
        except Exception as e:
            logger.error(f"readall() fallback also failed for {blob_name}: {str(e)}")
            raise
            
    except Exception as e:
        logger.error(f"Failed to download {blob_name}: {str(e)}")
        raise

def load_model_and_columns():
    """Load model and feature columns once and cache them globally"""
    global lr_model, feature_columns
    
    logger.info("Starting load_model_and_columns")
    
    if lr_model is not None and feature_columns is not None:
        logger.info("Model and columns already cached")
        return lr_model, feature_columns
    
    container_name = os.getenv('CONTAINER_NAME')
    if not container_name:
        raise ValueError("CONTAINER_NAME not found in environment variables")
    
    logger.info(f"Container name: {container_name}")
    
    try:
        # Load the model
        logger.info("Loading model...")
        model_blob_name = "models/linear_model.pkl"
        model_bytes = download_blob_content(container_name, model_blob_name)
        
        # Load model from bytes
        model_buffer = BytesIO(model_bytes)
        lr_model = cloudpickle.load(model_buffer)
        logger.info("Model loaded successfully")
        
        # Load feature columns
        logger.info("Loading feature columns...")
        columns_blob_name = "models/X_columns.json"
        columns_bytes = download_blob_content(container_name, columns_blob_name)
        
        # Parse JSON
        json_str = columns_bytes.decode('utf-8')
        feature_columns = json.loads(json_str)
        logger.info(f"Feature columns loaded successfully ({len(feature_columns)} columns)")
        
        return lr_model, feature_columns
        
    except Exception as e:
        logger.error(f"Error in load_model_and_columns: {str(e)}")
        traceback.print_exc()
        raise

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/health')
def health():
    """Health check endpoint"""
    try:
        # Try to load model to verify everything is working
        model, columns = load_model_and_columns()
        return {
            "status": "healthy",
            "model_loaded": model is not None,
            "columns_count": len(columns) if columns else 0
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}, 500

@app.route('/submit', methods=['POST'])
def submit():
    logger.info("Submit route called")
    try:
        # Get form data
        form_data = {}
        required_fields = ['location', 'sqft', 'bath', 'size']
        
        for field in required_fields:
            value = request.form.get(field)
            if not value:
                return f"Error: {field} is required", 400
            form_data[field] = value
        
        logger.info(f"Form data received: {form_data}")
        
        # Convert and validate numeric inputs
        try:
            form_data['sqft'] = float(form_data['sqft'])
            form_data['bath'] = int(form_data['bath'])
            form_data['size'] = int(form_data['size'])
        except ValueError as e:
            logger.error(f"Invalid numeric input: {str(e)}")
            return "Error: Invalid numeric input", 400
        
        # Validate ranges
        if form_data['sqft'] <= 0 or form_data['sqft'] > 50000:
            return "Error: Square feet must be between 1 and 50,000", 400
        if form_data['bath'] <= 0 or form_data['bath'] > 20:
            return "Error: Bathrooms must be between 1 and 20", 400
        if form_data['size'] <= 0 or form_data['size'] > 20:
            return "Error: Size (BHK) must be between 1 and 20", 400
        
        # Get prediction
        prediction = predict_price(form_data)
        logger.info(f"Prediction: {prediction}")
        
        return render_template('output.html', 
                             location=form_data['location'],
                             sqft=form_data['sqft'],
                             bath=form_data['bath'],
                             size=form_data['size'],
                             ans=round(prediction, 2))
                             
    except Exception as e:
        logger.error(f"Error in submit route: {str(e)}")
        traceback.print_exc()
        return f"Error processing request: {str(e)}", 500

def predict_price(form_data):
    """Make prediction using cached model and columns"""
    logger.info("predict_price called")
    try:
        # Load model and columns (cached after first load)
        model, columns = load_model_and_columns()
        
        # Extract input values
        location = form_data['location']
        sqft = form_data['sqft']
        bath = form_data['bath']
        bhk = form_data['size']
        
        logger.info(f"Prediction inputs: location={location}, sqft={sqft}, bath={bath}, bhk={bhk}")
        
        # Convert columns to numpy array for easier searching
        columns_array = np.array(columns)
        
        # Find location index
        loc_indices = np.where(columns_array == location)[0]
        logger.info(f"Location '{location}' found at indices: {loc_indices}")
        
        # Create feature vector
        x = np.zeros(len(columns))
        x[0] = sqft
        x[1] = bath
        x[2] = bhk
        
        # Set location feature if found
        if len(loc_indices) > 0:
            x[loc_indices[0]] = 1
            logger.info(f"Set location feature at index {loc_indices[0]}")
        else:
            logger.warning(f"Location '{location}' not found in feature columns")
        
        # Make prediction
        prediction = model.predict([x])[0]
        logger.info(f"Raw prediction: {prediction}")
        
        return prediction
        
    except Exception as e:
        logger.error(f"Error in predict_price: {str(e)}")
        traceback.print_exc()
        raise

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 error: {error}")
    return "Internal server error occurred. Please try again later.", 500

@app.errorhandler(404)
def not_found(error):
    return "Page not found", 404

# @app.before_first_request
# def initialize():
#     """Initialize the application"""
#     try:
#         logger.info("Initializing application...")
#         load_model_and_columns()
#         logger.info("Application initialized successfully")
#     except Exception as e:
#         logger.error(f"Failed to initialize application: {str(e)}")
#         # Don't raise here to allow the app to start, but log the error

if __name__ == '__main__':
    # Set up logging for development
    if os.getenv('FLASK_ENV') == 'development':
        app.config['DEBUG'] = True
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("Starting Flask application")
    
    # Try to pre-load model
    try:
        load_model_and_columns()
        logger.info("Model pre-loaded successfully")
    except Exception as e:
        logger.warning(f"Could not pre-load model: {str(e)}")
    
    port = int(os.getenv('PORT', 5000))
    logger.info(f"Starting server on port {port}")
    
    app.run(host='0.0.0.0', port=port, debug=True)
