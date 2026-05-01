# Cloud Project
**Workflow**

Run the init script to set up and start the project.

_The script:_

1. Installs Python and required packages from requirements.txt
2. Creates a .env file
3. Sets up Gunicorn in the VM
4. Starts the Flask app (flaskapp.py)

_Parameters:_

Provide these while running the script:

* CONNECTION_STRING
* CONTAINER_NAME
* PORT
  
_Run:_

./init.sh "<CONNECTION_STRING>" "<CONTAINER_NAME>" "<PORT>"

_Access:_
http://<VM_IP>:<PORT>
