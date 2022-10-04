#!/usr/bin/env python3

import socket
import select
import sys

# Create a TCP/IP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Bind the socket to the port
server_address = ('localhost', 5000)
print(f"starting up on {server_address[0]} port {server_address[1]}", file=sys.stderr)
sock.bind(server_address)

# Listen for incoming connections
sock.listen(1)

while True:
    # Wait for a connection
    print("waiting for a connection", file=sys.stderr)
    connection, client_address = sock.accept()
    print(f"connection from {client_address}", file=sys.stderr)

    try:
        # Receive the data in small chunks and retransmit it
        while True:
            rlist = select.select([connection], [], [])[0]

            if connection in rlist:
                data = connection.recv(16)

                if data:
                    print(f"received: {data}", file=sys.stderr)
                    connection.sendall(data)
                else:
                    print(f"no more data from {client_address}", file=sys.stderr)
                    break
            
    finally:
        # Clean up the connection
        connection.close()
        print("Connection closed")
