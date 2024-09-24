#!/usr/bin/env python3

# pqsim51  - simulate proqa medical on localhost port 5100

import socket
import select
import sys

eomstring = "</comm>"

connections = []
sock51 = None
sock52 = None
sock53 = None

try:
    sock51 = socket.create_server(('localhost', 5100), backlog=3)
    connections.append(sock51)
    print("Socket created, bound and listening on localhost port 5100")

    sock52 = socket.create_server(('localhost', 5200), backlog=3)
    connections.append(sock52)
    print("Socket created, bound and listening on localhost port 5200")

    sock53 = socket.create_server(('localhost', 5300), backlog=3)
    connections.append(sock53)
    print("Socket created, bound and listening on localhost port 5300")

    # Wait for a connection
    while True:
        rlist = select.select(connections, [], [],0.5)[0]  # only get readable sockets, not writable or error

        for c in connections:
            if c in rlist:
                #print(c)

                if c == sock51 or c == sock52 or c == sock53:
                    con, client_address = c.accept()
                    connections.append(con)

                    if c == sock51:
                        print(f"connection on 5100 from {client_address}", file=sys.stderr)
                    elif c == sock52:
                        print(f"connection on 5200 from {client_address}", file=sys.stderr)
                    elif c == sock53:
                        print(f"connection on 5300 from {client_address}", file=sys.stderr)

                # Data on an active connection
                else:
                    print(f"Receiving message from client on {c.getsockname()[1]}")
                    fulldata=""

                    # Receive the data in small chunks and retransmit it
                    while True:
                        data = c.recv(16)  # Receive data in chunks of 16 bytes

                        if data:
                            print(f"received chunk from client on {c.getsockname()[1]}: {data}", file=sys.stderr)
                            fulldata += data.decode('utf-8')  # Accumulate the received data

                            if eomstring in fulldata:
                                print("End of Msg received.")

                                if fulldata:
                                    print(f"Complete message client on {c.getsockname()[1]}: {fulldata}", file=sys.stderr)

                                sendresponse=f"From {c.getsockname()[1]}: {fulldata}{eomstring}".encode('utf-8')
                                fulldata=""

                                try:
                                    c.sendall(sendresponse)  
                                except OSError as e:
                                    print(f"Error sending response to client on {c.getsockname()[1]}: {e}")
                                
                                break  # Exit the loop


                        else:
                            print(f"Connection to client on {c.getsockname()[1]} closed by client")
                            c.close()
                            connections.remove(c)
                            break

except KeyboardInterrupt:
    print("Received interrupt signal, exiting")

except OSError as e:
    print(f"Exception: {e}")

finally:
    # Clean up the connection
    for c in connections:
        if c:
            c.close()
    print("Connections closed")

sys.exit(0)
