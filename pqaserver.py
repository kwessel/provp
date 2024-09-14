#!/usr/bin/env python3

# copied from c:\keith3\vpcom_server.py

#  pqaserver - run as service  systemd  on rms. server folder /home/brownlee/services  

import socket
import select
import sys
import argparse

# Global constants
CAD_MSG_TERMINATOR = "</comm>"
MAX_OPERATORS = 10
cadport = 6001
pqaport = 6000

# Define command-line arguments
parser = argparse.ArgumentParser(
    description="Relay CAD messages to vpcom clients"
    )

#-d / --debug
parser.add_argument("-d", "--debug", dest="debug", default=False,
                    action="store_true", help="enable debugging outputs")

#--cad-host
parser.add_argument("--cad-host", dest="cad_host",
                    default="0.0.0.0",
                    help="IP address where CAD will send messages")

#--cad-port
parser.add_argument("--cad-port", dest="cad_port",
                    default=cadport, type=int,
                    help="port where CAD will send messages")

#--pqa-host
parser.add_argument("--pqa-host", dest="pqa_host",
                    default="0.0.0.0",
                    help="IP address that pqaclients connect to")

#--pqa-port
parser.add_argument("--pqa-port", dest="pqa_port", type=int,
                    default=pqaport,
                    help="port to listen on for connections from pqaclients")

#parse arguments
options = parser.parse_args()

debug = options.debug

if debug:
    print("Processed command-line arguments:")
    print(options)

cad_host = options.cad_host
cad_port = options.cad_port
pqa_host = options.pqa_host
pqa_port = options.pqa_port

debug and print(f"starting up on {cad_host}:{cad_port} and {pqa_host}:{pqa_port}", file=sys.stderr)

try:
    # Create a socket, bind to the port, and start listening for connections
    cad_sock = socket.create_server((cad_host, cad_port), backlog=3)
    print(f"Listening for connections from CAD on {cad_host}:{cad_port}")
except OSError as e:
    print(f"Failed to create server on port {cad_port}: {e}")
    sys.exit(1)

try:
    # Create a socket, bind to the port, and start listening for connections
    pqa_sock = socket.create_server((pqa_host, pqa_port), backlog=3)
    print(f"Listening for connections from pqaclients  on {pqa_host}:{pqa_port}")
except OSError as e:
    print(f"Failed to create server on port {pqa_port}: {e}")
    sys.exit(1)

# Create list of connections to listen on
connections = [cad_sock, pqa_sock]

# Create dictionary to map operator numbers to open sockets
operators = {}

# Wait for a connection
while True:
    try:
        debug and print("waiting for a connection", file=sys.stderr)
        rlist = select.select(connections, [], [])[0]

        # New message from CAD to send to a client
        if cad_sock in rlist:
            cad_conn, client_address = cad_sock.accept()
            cad_conn.settimeout(1)
            debug and print(f"connection from CAD on {client_address}", file=sys.stderr)

            recipient = None
            cad_msg = ""

            while True:
                try:
                    data = cad_conn.recv(16)
                except socket.timeout:
                    debug and print("No data received from CAD before timeout, closing connection")
                    cad_conn.shutdown(socket.SHUT_RDWR)
                    cad_conn.close()
                    break

                if data:
                    debug and print(f"received from CAD: {data}")

                    # Have we received the destination operator yet?
                    if not recipient:
                        recipient = data.decode('utf-8').rstrip()

                        # Did we get a number?
                        if not recipient.isdigit():
                            print(f"Received invalid operator ID from CAD: {recipient}")
                            cad_conn.shutdown(socket.SHUT_RDWR)
                            cad_conn.close()
                            break

                        # Is this operator currently connected?
                        elif not recipient in operators:
                            print(f"Received non-existent operator ID from CAD: {recipient}")
                            cad_conn.sendall("No such operator\n".encode('utf-8'))
                            cad_conn.shutdown(socket.SHUT_RDWR)
                            cad_conn.close()
                            break

                        # Recipient is valid and currently connected
                        else:
                            print(f"Receiving message for operator {recipient}")

                    # We received the operator, this is the message
                    else:
                        cad_msg += data.decode('utf-8')

                        # Is this the end of the message?
                        if CAD_MSG_TERMINATOR in cad_msg:
                            debug and print(f"Sending to {recipient}: {cad_msg}")
                            operators[recipient].sendall(cad_msg.encode('utf-8'))

                            try:
                                resp = operators[recipient].recv(4)
                            except OSError as e:
                                resp = None

                            if resp and resp.decode('utf-8').rstrip() == "OK":
                                print(f"Message acknowledged by Operator {recipient}")
                                cad_conn.sendall("OK\n".encode('utf-8'))

                            else:
                                print("Operator {recipient} didn't acknowledge message, closing connection to client")
                                operators[recipient].shutdown(socket.SHUT_RDWR)
                                operators[recipient].close()
                                try:
                                    connections.remove(operators[recipient])
                                    del operators[recipient]
                                except KeyError:
                                    pass

                                cad_conn.sendall("NO\n".encode('utf-8'))

                            cad_conn.shutdown(socket.SHUT_RDWR)
                            cad_conn.close()
                            break

                # Or see that the server closed the connection without finishing
                else:
                    debug and print("CAD closed connection without sending terminator")
                    break

        # New connection from a client
        if pqa_sock in rlist:
            pqa_conn, client_address = pqa_sock.accept()
            pqa_conn.settimeout(1)
            print(f"New client connection from {client_address[0]}")

            try:
                data = pqa_conn.recv(16)
            except socket.timeout:
                print("No data received from client before timeout, closing connection")
                pqa_conn.shutdown(socket.SHUT_RDWR)
                pqa_conn.close()
                continue

            if data:
                op = data.decode('utf-8').rstrip()

                # Make sure operator identified itself with a number
                if op.isdigit():
                    if op in operators:
                        print(f"Rejecting connection from {client_address[0]} identified as already connected operator {op}")
                        pqa_conn.sendall("Operator already connected\n".encode('utf-8'))
                        pqa_conn.shutdown(socket.SHUT_RDWR)
                        pqa_conn.close()
                    else:
                        print(f"Operator {op} connected from {client_address[0]}")
                        pqa_conn.sendall("OK\n".encode('utf-8'))

                        # Record this open connection and the associated operator
                        operators[op] = pqa_conn
                        connections.append(operators[op])
                else:
                    print(f"Rejecting connection from {client_address[0]} that sent garbage")
                    pqa_conn.shutdown(socket.SHUT_RDWR)
                    pqa_conn.close()

            else:
                print(f"Client on {client_address[0]} closed connection before identifying itself")

        for op in operators.keys():
            conn = operators[op]
            if conn in rlist:
                data = conn.recv(1)

                # Client has closed connection
                if not data:
                    print(f"Operator {op} disconnected")
                    try:
                        connections.remove(operators[op])
                        del operators[op]
                    except KeyError:
                        pass
                    break

        if pqa_sock in connections and len(operators) >= MAX_OPERATORS:
            print (f"Reached max number of operator connections {MAX_OPERATORS}, not accepting more")
            connections.remove(pqa_sock)
        elif pqa_sock not in connections and len(operators) < MAX_OPERATORS:
            print (f"Connections below max number of operator connections {MAX_OPERATORS}, accepting connections again")
            connections.append(pqa_sock)

    except OSError as e:
        print(f"Ignoring unhandled socket or IO error: {e}")

    except KeyboardInterrupt:
        debug and print("Received interrupt signal, exiting")
        break

# Clean up the connection
for sock in connections:
    sock.shutdown(socket.SHUT_RDWR)
    sock.close()
print("Exiting, all onnections closed")

sys.exit(0)
