#!/usr/bin/env python3

# pqserver  - upload to /home/brownlee/services
#  . run from putty window  /home/brownlee/services   python3 pqserver.py  
#  . chmod -R 755 pqserver.py   from /home/brownlee/services

# Run as a service:   pqserver.service  uploaded to  /home/brownlee/.local/share/systemd/user
#  . systemctl --user daemon-reload        after uploading new servicefile   
#  . systemctl --user start pqserver       start pqserver  
#  . systemctl --user restart pqserver     after a file upload - overwriting existing file
#  . systemctl --user enable pqserver      makes pqserver auto-start on server boot


import socket
import select
import sys
import argparse

#Global variables
debug = True  # Enable debugging messages
eomstring = "</comm>"
maxoperators= 10

# Command-line defaults
cadhost='0.0.0.0'
cadport = 6001
clienthost='0.0.0.0'
clientport = 6000

# Exceptions to throw
class pqserverexception(Exception):
    pass

def parsecmdline():
    """parsecmdline() -- parses cmd-line arguments

    Params:
    None

    Throws:
    None

    Returns:
    options -- dictionary of selected command-line options
    """

    # Since we'll be updating it later, use the global debug variable
    global debug

    # Define command-line arguments
    parser = argparse.ArgumentParser(
        description="Relay CAD messages to pqclient clients"
        )

    #-d / --debug
    parser.add_argument("-d", "--debug", dest="debug", default=debug,
                        action="store_true", help="enable debugging outputs")

    #--cad-host
    parser.add_argument("--cad-host", dest="cadhost",
                        default=cadhost,
                        help="IP address where CAD will send messages")

    #--cad-port
    parser.add_argument("--cad-port", dest="cadport",
                        default=cadport, type=int,
                        help="port where CAD will send messages")

    #--clienthost
    parser.add_argument("--clienthost", dest="clienthost",
                        default=clienthost,
                        help="IP address that pqclients connect to")

    #--clientport
    parser.add_argument("--clientport", dest="clientport", type=int,
                        default=clientport,
                        help="port to listen on for connections from pqclients")

    #parse arguments
    options = parser.parse_args()

    # Set global debug setting from command-line options
    debug = options.debug

    if debug:
        print("Processed command-line arguments:")
        print(options)

    return options

def closeall(connections):
    """closeall() -- Close all connections in the supplied list

    Params:
    connections -- list of connections to try to close

    Throws:
    None

    Returns:
    None
    """

    for sock in connections:
        if sock:
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
    print("Exiting, all connections closed")

def startserver(name, host, port):
    """startserver() -- Create a socket for a listening server

    Params:
    name -- human-friendly name of the server
    host -- IP address to listen for connections on
    port -- TCP port to listen for connections on

    Throws:
    pqserverexception if socket can't be established

    Returns:
    File descriptor of newly created socket
    """

    try:
        sock = socket.create_server((host, port), backlog=3)
        print(f"Listening for connections from {name} on {host}:{port}")
        return sock
    except OSError as e:
        raise pqserverexception(f"Failed to create {name} server on {host}:{port}: {e}")

if __name__ == "__main__":
    options = parsecmdline()

    # Create list of connections to listen on
    connections = []

    # Create dictionary to map operator numbers to open sockets
    operators = {}

    cadsock = None
    clientsock = None

    debug and print(f"Listening for cad on {options.cadhost}:{options.cadport} and client on {options.clienthost}:{options.clientport}", file=sys.stderr)

    #  setup sockets on localhost ports 6000 and 6001, bind, listen for cad and pqaclients
    try:
        cadsock = startserver("CAD", options.cadhost, options.cadport)
        connections.append(cadsock)

        clientsock = startserver("pqclients", clienthost, clientport)
        connections.append(clientsock)

    except pqserverexception as e:
        print(e)
        closeall(connections)
        sys.exit(1)

    # Wait for a connection
    while True:
        try:
            debug and print("waiting for a connection", file=sys.stderr)
            rlist = select.select(connections, [], [])[0]
            
            # ==========================================================
            # New message from CAD to send to a client
            # ==========================================================

            if cadsock in rlist:
                cadcon, client_address = cadsock.accept()
                cadcon.settimeout(1)
                debug and print(f"connection from CAD on {client_address}", file=sys.stderr)

                recipient = None
                cadmsg = ""

                while True:
                    try:
                        data = cadcon.recv(16)
                    except socket.timeout:
                        debug and print("No data received from CAD before timeout, closing connection")
                        cadcon.shutdown(socket.SHUT_RDWR)
                        cadcon.close()
                        break

                    if data:
                        debug and print(f"received from CAD: {data}")
                        
                        # Have we received the station# yet?
                        if not recipient:
                            # Read first line of input containing one or more digits
                            recipient = data.decode('utf-8').rstrip()  # remove spaces and \n

                            # Did we get a number?  first line from cad is station# 1-9 and \n
                            if not recipient.isdigit():
                                print(f"Received invalid operator ID from CAD: {recipient}")
                                cadcon.shutdown(socket.SHUT_RDWR)
                                cadcon.close()
                                break

                            # Is this operator currently connected?  connected by pqaclient when starting
                            elif not recipient in operators:
                                print(f"Received non-existent operator ID from CAD: {recipient}")
                                cadcon.sendall("No such operator\n".encode('utf-8'))
                                cadcon.shutdown(socket.SHUT_RDWR)
                                cadcon.close()
                                break

                            # Recipient is valid and currently connected
                            else:
                                print(f"Receiving message for operator {recipient}")

                        # We received the operator, this is the message
                        else:
                            cadmsg += data.decode('utf-8')
                            
                            # Is this the end of the message?
                            if eomstring in cadmsg:
                                debug and print(f"Sending to {recipient}: {cadmsg}")
                                
                                operators[recipient].sendall(cadmsg.encode('utf-8'))

                                try:
                                    resp = operators[recipient].recv(4)
                                except OSError as e:
                                    resp = None

                                if resp and resp.decode('utf-8').rstrip() == "OK":
                                    print(f"Message acknowledged by Operator {recipient}")
                                    cadcon.sendall("OK\n".encode('utf-8'))

                                else:
                                    print("Operator {recipient} didn't acknowledge message, closing connection to client")
                                    operators[recipient].shutdown(socket.SHUT_RDWR)
                                    operators[recipient].close()
                                    try:
                                        connections.remove(operators[recipient])
                                        del operators[recipient]
                                    except KeyError:
                                        pass

                                    cadcon.sendall("NO\n".encode('utf-8'))

                                cadcon.shutdown(socket.SHUT_RDWR)
                                cadcon.close()
                                break

                    # Or see that the server closed the connection without finishing
                    else:
                        debug and print("CAD closed connection without sending terminator")
                        break
                        
            # ======================================================================================
            # New connection from a pqclient  - sent when pqclient.exe launches from c:\vproute
            # ======================================================================================       
            
            if clientsock in rlist:
                clientcon, client_address = clientsock.accept()
                clientcon.settimeout(1)
                print(f"New client connection from {client_address[0]}")

                try:
                    data = clientcon.recv(16)
                except socket.timeout:
                    print("No data received from client before timeout, closing connection")
                    clientcon.shutdown(socket.SHUT_RDWR)
                    clientcon.close()
                    continue

                if data:
                    op = data.decode('utf-8').rstrip()

                    # Make sure operator identified itself with a number
                    if op.isdigit():
                        if op in operators:
                            print(f"Rejecting connection from {client_address[0]} identified as already connected operator {op}")
                            clientcon.sendall("Operator already connected\n".encode('utf-8'))
                            clientcon.shutdown(socket.SHUT_RDWR)
                            clientcon.close()
                        else:
                            print(f"Operator {op} connected from {client_address[0]}")
                            clientcon.sendall("OK\n".encode('utf-8'))

                            # Record this open connection and the associated operator
                            operators[op] = clientcon
                            connections.append(operators[op])
                    else:
                        print(f"Rejecting connection from {client_address[0]} that sent garbage")
                        clientcon.shutdown(socket.SHUT_RDWR)
                        clientcon.close()

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

            if clientsock in connections and len(operators) >= maxoperators:
                print (f"Reached max number of operator connections {maxoperators}, not accepting more")
                connections.remove(clientsock)
            elif clientsock not in connections and len(operators) < maxoperators:
                print (f"Connections below max number of operator connections {maxoperators}, accepting connections again")
                connections.append(clientsock)

        except OSError as e:
            print(f"Ignoring unhandled socket or IO error: {e}")

        except KeyboardInterrupt:
            debug and print("Received interrupt signal, exiting")
            break

        finally:
            closeall(connections)

    sys.exit(0)
