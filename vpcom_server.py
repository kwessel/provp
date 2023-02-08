#!/usr/bin/env python3

import socket
import select
import sys
import argparse

# Global constants
CAD_MSG_TERMINATOR = "</comm>"
MAX_OPERATORS = 10
CAD_PORT = 5001
VPCOM_PORT = 5000

# Define command-line arguments
parser = argparse.ArgumentParser(
    description="Relay CAD messages to vpcom clients"
    )

#-d / --debug
parser.add_argument("-d", "--debug", dest="debug", default=False,
                    action="store_true", help="enable debugging outputs")

#--cad-host
parser.add_argument("--cad-host", dest="cad_host",
                    default="localhost",
                    help="IP address where CAD will send messages")

#--cad-port
parser.add_argument("--cad-port", dest="cad_port",
                    default=CAD_PORT, type=int,
                    help="port where CAD will send messages")

#--vpcom-host
parser.add_argument("--vpcom-host", dest="vpcom_host",
                    default="0.0.0.0",
                    help="IP address that vpcom clients connect to")

#--vpcom-port
parser.add_argument("--vpcom-port", dest="vpcom_port", type=int,
                    default=VPCOM_PORT,
                    help="port to listen on for connections from vpcom clients")

#parse arguments
options = parser.parse_args()

debug = options.debug

if debug:
    print("Processed command-line arguments:")
    print(options)

cad_host = options.cad_host
cad_port = options.cad_port
vpcom_host = options.vpcom_host
vpcom_port = options.vpcom_port

debug and print(f"starting up on {cad_host}:{cad_port} and {vpcom_host}:{vpcom_port}", file=sys.stderr)

try:
    # Create a socket, bind to the port, and start listening for connections
    cad_sock = socket.create_server((cad_host, cad_port), backlog=0)
    print(f"Listening for connections from CAD on {cad_host}:{cad_port}")
except OSError as e:
    print(f"Failed to create server on port {cad_port}: {e}")
    sys.exit(1)

try:
    # Create a socket, bind to the port, and start listening for connections
    vpcom_sock = socket.create_server((vpcom_host, vpcom_port), backlog=0)
    print(f"Listening for connections from VPCom clients  on {vpcom_host}:{vpcom_port}")
except OSError as e:
    print(f"Failed to create server on port {vpcom_port}: {e}")
    sys.exit(1)

# Create list of connections to listen on
connections = [cad_sock, vpcom_sock]

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
        if vpcom_sock in rlist:
            vpcom_conn, client_address = vpcom_sock.accept()
            vpcom_conn.settimeout(1)
            print(f"New client connection from {client_address[0]}")

            try:
                data = vpcom_conn.recv(16)
            except socket.timeout:
                print("No data received from client before timeout, closing connection")
                vpcom_conn.shutdown(socket.SHUT_RDWR)
                vpcom_conn.close()
                continue

            if data:
                op = data.decode('utf-8').rstrip()

                # Make sure operator identified itself with a number
                if op.isdigit():
                    if op in operators:
                        print(f"Rejecting connection from {client_address[0]} identified as already connected operator {op}")
                        vpcom_conn.sendall("Operator already connected\n".encode('utf-8'))
                        vpcom_conn.shutdown(socket.SHUT_RDWR)
                        vpcom_conn.close()
                    else:
                        print(f"Operator {op} connected from {client_address[0]}")
                        vpcom_conn.sendall("OK\n".encode('utf-8'))

                        # Record this open connection and the associated operator
                        operators[op] = vpcom_conn
                        connections.append(operators[op])
                else:
                    print(f"Rejecting connection from {client_address[0]} that sent garbage")
                    vpcom_conn.shutdown(socket.SHUT_RDWR)
                    vpcom_conn.close()

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

        if vpcom_sock in connections and len(operators) >= MAX_OPERATORS:
            print (f"Reached max number of operator connections {MAX_OPERATORS}, not accepting more")
            connections.remove(vpcom_sock)
        elif vpcom_sock not in connections and len(operators) < MAX_OPERATORS:
            print (f"Connections below max number of operator connections {MAX_OPERATORS}, accepting connections again")
            connections.append(vpcom_sock)

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
