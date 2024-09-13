#!/usr/bin/env python3

import socket
import select
import requests
from requests.exceptions import RequestException
import sys
import argparse

# Global constants
PROQA_MSG_TERMINATOR = "</conn>"
CATCHPRO_URL = "http://www.brownleedatasystems.com/i/catchpro.php"
CATCHPRO_TIMEOUT = 10

# Define command-line arguments
parser = argparse.ArgumentParser(
    description="Bridge communications between CAD and ProQA"
    )

#-d / --debug
parser.add_argument("-d", "--debug", dest="debug", default=False,
                    action="store_true", help="enable debugging outputs")

#--proqa-host
parser.add_argument("--proqa-host", dest="proqa_host",
                    default="localhost",
                    help="hostname where ProQA is running")

#--proqa-port
parser.add_argument("--proqa-port", dest="proqa_port",
                    default=5000, type=int,
                    help="port where ProQA is running")

#--provp-host
parser.add_argument("--provp-host", dest="provp_host",
                    default="0.0.0.0",
                    help="address to listen on for connections from CAD")

#--provp-port
parser.add_argument("--provp-port", dest="provp_port", type=int,
                    default=5001,
                    help="port to listen on for connections from CAD")

#--catchpro-url
parser.add_argument("-u", "--catchpro-url", dest="catchpro_url",
                    default=CATCHPRO_URL,
                    help="URL to POST ProQA messages to")
#parse arguments
options = parser.parse_args()

debug = options.debug

if debug:
    print("Processed command-line arguments:")
    print(options)

proqa_host = options.proqa_host
proqa_port = options.proqa_port
provp_host = options.provp_host
provp_port = options.provp_port
catchpro_url = options.catchpro_url

try:
    proqa_conn = socket.create_connection((proqa_host, proqa_port))
except OSError as e:
    print(f"Failed to connect to ProQA on {proqa_host}:{proqa_port}: {e}")
    sys.exit(1)

debug and print(f"starting up on {provp_host} port {provp_port}")

try:
    # Create a socket, bind to the port, and start listening for connections
    sock = socket.create_server((provp_host, provp_port), backlog=1)
    sock_fd = sock.fileno()
except OSError as e:
    print(f"Failed to create server on port {provp_port}: {e}")
    sys.exit(2)

# Wait for a connection
while True:
    debug and print("waiting for a connection or data from ProQA")
    try:
        # Wait for data to read from either CAD or ProQA
        rlist = select.select([sock_fd, proqa_conn], [], [])[0]

        # If new client connection, connect and send data to the server
        if sock_fd in rlist:
            cad_conn, client_address = sock.accept()
            debug and print(f"New connection from client: {client_address[0]}")

            # Keep reading from client until there's no more to read
            while True:
                try:
                    data = cad_conn.recv(16)

                    if data:
                        debug and print(f"Received from CAD: {data}")
                        proqa_conn.sendall(data)
                    # Or see that the client closed the connection
                    else:
                        debug and print("Connection closed by CAD")
                        cad_conn.close()
                        break

                except OSError as e:
                    print(f"Error exchanging communications between CAD and ProQA: {e}")

        # If the data is from the server, post it to catchpro_url
        if proqa_conn in rlist:
            proqa_msg = ""

            while True:
                data = proqa_conn.recv(16)

                if data:
                    debug and print(f"received from ProQA: {data}")
                    proqa_msg += data.decode('utf-8')

                    # Is this the end of the ProQA message?
                    if PROQA_MSG_TERMINATOR in proqa_msg:
                        break

                # Or see that the server closed the connection
                else:
                    debug and print("ProQA has closed the connection")
                    sock.close()
                    sys.exit(3)

            if proqa_msg:
                debug and print(f"posting to catchpro_url: {proqa_msg}")
                form_data = {'msg': proqa_msg}
                try:
                    resp = requests.post(catchpro_url, data=form_data,
                           timeout=CATCHPRO_TIMEOUT)
                    debug and print(f"HTTP post returned status {resp.status_code}")

                except RequestException as e:
                    debug and print(f"Failed to post to {catchpro_url}: {e}")
            
    except KeyboardInterrupt:
        debug and print("Received interrupt signal, exiting")
        break

# Clean up the connection
sock.close()
proqa_conn.close()
debug and print("Connection closed")

sys.exit(0)
