#!/usr/bin/env python3

import socket
import select
import sys
import argparse

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

debug and print(f"starting up on {provp_host} port {provp_port}", file=sys.stderr)

try:
    # Create a socket, bind to the port, and start listening for connections
    sock = socket.create_server((provp_host, provp_port), backlog=1)
except OSError as e:
    print(f"Failed to create server on port {provp_port}: {e}")
    sys.exit(1)

# Wait for a connection
while True:
    debug and print("waiting for a connection", file=sys.stderr)
    try:
        cad_conn, client_address = sock.accept()
    except KeyboardInterrupt:
        debug and print("Received interrupt signal, exiting")
        sock.close()
        sys.exit(0)

    debug and print(f"connection from {client_address}", file=sys.stderr)

    try:
        proqa_conn = socket.create_connection((proqa_host, proqa_port))
    except OSError as e:
        print(f"Failed to connect to ProQA: {e}")
        cad_conn.close()
        continue

    # Receive the data in small chunks and retransmit it
    try:
        # Wait for data to read from either CAD or ProQA
        while True:
            rlist = select.select([cad_conn, proqa_conn], [], [])[0]

            # If the data is from the client, send it to the server
            if cad_conn in rlist:
                data = cad_conn.recv(16)

                if data:
                    debug and print(f"sending to ProQA: {data}", file=sys.stderr)
                    proqa_conn.sendall(data)
                # Or see that the client closed the connection
                else:
                    debug and print("no more data from CAD", file=sys.stderr)
                    break
            
            # If the data is from the server, send it to the client
            if proqa_conn in rlist:
                data = proqa_conn.recv(16)

                if data:
                    debug and print(f"sending to CAD: {data}", file=sys.stderr)
                    cad_conn.sendall(data)
                # Or see that the server closed the connection
                else:
                    debug and print("no more data from ProQA", file=sys.stderr)
                    break
            
    except OSError as e:
        print(f"Error exchanging communications between CAD and ProQA: {e}")

    except KeyboardInterrupt:
        debug and print("Received interrupt signal, exiting")
        break

    finally:
        # Clean up the connection
        cad_conn.close()
        proqa_conn.close()
        debug and print("Connection closed")

sys.exit(0)
