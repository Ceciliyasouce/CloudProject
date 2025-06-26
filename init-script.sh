#!/bin/bash

# Install system packages
sudo apt-get update -y
sudo apt upgrade -y

sudo apt install -y build-essential libssl-dev zlib1g-dev \
libncurses5-dev libncursesw5-dev libreadline-dev \
libsqlite3-dev libgdbm-dev libdb5.3-dev libbz2-dev \
libexpat1-dev liblzma-dev tk-dev libffi-dev wget

sudo wget https://www.python.org/ftp/python/3.9.6/Python-3.9.6.tgz

sudo tar -xvzf Python-3.9.6.tgz

cd Python-3.9.6

sudo ./configure --enable-optimizations

make -j $(nproc)

sudo make altinstall

# Clone your GitHub repo
cd /home/azureuser
git clone https://github.com/Ceciliyasouce/CloudProject.git flaskapp
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
