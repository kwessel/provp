#!/usr/bin/env python3

# pqsim51  - simulate proqa medical on localhost port 5100

import socket
import select
import sys

eomstring = "</comm>"

sock51 = socket.create_server(('localhost', 5100), backlog=3)
print("Socket created, bound and listening on localhost port 5100")

sock52 = socket.create_server(('localhost', 5200), backlog=3)
print("Socket created, bound and listening on localhost port 5200")

sock53 = socket.create_server(('localhost', 5300), backlog=3)
print("Socket created, bound and listening on localhost port 5300")

connections = [sock51, sock52, sock53]

while True:
    # Wait for a connection
    try:
        rlist = select.select(connections, [], [],0.5)[0]  # only get readable sockets, not writable or error

        for c in rlist:
            if c == sock51 or c == sock52 or c == sock53:
                conn, client_address = c.accept()
                connections.append(conn)

                if c == sock51:
                    print(f"connection on 5100 from {client_address}", file=sys.stderr)
                elif c == sock52:
                    print(f"connection on 5200 from {client_address}", file=sys.stderr)
                elif c == sock53:
                    print(f"connection on 5300 from {client_address}", file=sys.stderr)

            # Data on an active connection
            else:
                fulldata=b''

                # Receive the data in small chunks and retransmit it
                while True:
                    data = c.recv(16)  # Receive data in chunks of 16 bytes

                    if data:
                        fulldata += data  # Accumulate the received data

                        if eomstring in data.decode('utf-8'):
                            print("End of Msg received.")

                            # Decode the accumulated bytes data and print it as a string
                            if fulldata:
                                print(f"Complete message: {fulldata.decode('utf-8')}", file=sys.stderr)

                            sendresponse='From Pqsim51: '.encode('utf-8')+fulldata+eomstring.encode('utf-8')
                            try:
                                c.sendall(sendresponse)  
                            except OSError as e:
                                print(f"Error sending response: {e}")
                            
                            break  # Exit the loop

                        print(f"received chunk: {data}", file=sys.stderr)

                    else:
                        print("Connection closed by client")
                        c.close()
                        connections.remove(c)
                        break

    except KeyboardInterrupt:
        print("Received interrupt signal, exiting")
        break

# Clean up the connection
for c in connections:
    c.close()

print("Connections closed")
sys.exit(0)
