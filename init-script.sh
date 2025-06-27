#!/bin/bash

set -e  # Exit on any error

# Log everything
exec > >(tee -a /var/log/init-script.log) 2>&1
echo "Starting init script at $(date)"

# Install system packages
echo "Installing system packages..."
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install -y build-essential libssl-dev zlib1g-dev \
    libncurses5-dev libncursesw5-dev libreadline-dev \
    libsqlite3-dev libgdbm-dev libdb5.3-dev libbz2-dev \
    libexpat1-dev liblzma-dev tk-dev libffi-dev wget git

# Install Python 3.9.6
echo "Installing Python 3.9.6..."
cd /tmp
sudo wget https://www.python.org/ftp/python/3.9.6/Python-3.9.6.tgz
sudo tar -xvzf Python-3.9.6.tgz
cd Python-3.9.6
sudo ./configure --enable-optimizations
sudo make -j $(nproc)
sudo make altinstall

# Create symbolic links for easier access
sudo ln -sf /usr/local/bin/python3.9 /usr/local/bin/python3
sudo ln -sf /usr/local/bin/pip3.9 /usr/local/bin/pip3

# Verify Python installation
echo "Python version: $(python3 --version)"
echo "Pip version: $(pip3 --version)"

# Clone your GitHub repo
echo "Cloning GitHub repository..."
cd /home/azureuser
sudo -u azureuser git clone https://github.com/Ceciliyasouce/CloudProject.git flaskapp
cd flaskapp
sudo chown -R azureuser:azureuser /home/azureuser/flaskapp

# Install dependencies
echo "Installing Python dependencies..."
sudo -u azureuser pip3 install -r requirements.txt
sudo -u azureuser pip3 install gunicorn

# Verify environment variables
echo "Checking environment variables..."
echo "CONNECTION_STRING: ${CONNECTION_STRING:-'Not set'}"
echo "CONTAINER_NAME: ${CONTAINER_NAME:-'Not set'}"
echo "PORT: ${PORT:-'Not set'}"

# Create .env file
echo "Creating .env file..."
sudo -u azureuser cat <<EOF > .env
CONNECTION_STRING=${CONNECTION_STRING}
CONTAINER_NAME=${CONTAINER_NAME}
PORT=${PORT:-5000}
EOF

# Set proper permissions
sudo chown azureuser:azureuser .env
sudo chmod 600 .env

# Create systemd service for the Flask app
echo "Creating systemd service..."
sudo tee /etc/systemd/system/flaskapp.service > /dev/null <<EOF
[Unit]
Description=Flask Application
After=network.target

[Service]
Type=simple
User=azureuser
WorkingDirectory=/home/azureuser/flaskapp
Environment=PATH=/usr/local/bin:/usr/bin:/bin
EnvironmentFile=/home/azureuser/flaskapp/.env
ExecStart=/usr/local/bin/gunicorn -w 2 -b 0.0.0.0:${PORT:-5000} app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
echo "Starting Flask application service..."
sudo systemctl daemon-reload
sudo systemctl enable flaskapp.service
sudo systemctl start flaskapp.service

# Check service status
sleep 5
sudo systemctl status flaskapp.service

echo "Init script completed successfully at $(date)"
echo "Flask app should be running on port ${PORT:-5000}"
