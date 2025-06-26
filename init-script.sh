#!/bin/bash

# Install system packages
sudo apt-get update -y
sudo apt-get install -y python3-pip git

# Clone your GitHub repo
cd /home/azureuser
git clone https://github.com/your-username/your-repo.git flaskapp
cd flaskapp

# Install dependencies
pip3 install -r requirements.txt

# Write .env file from passed values
cat <<EOF > .env
CONNECTION_STRING=${CONNECTION_STRING}
CONTAINER_NAME=${CONTAINER_NAME}
EOF

# Run the app with gunicorn
nohup gunicorn -w 2 -b 0.0.0.0:${PORT} app:app &
