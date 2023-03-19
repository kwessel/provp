#!/usr/bin/env python3

#  vpcom - read from cad3 on cadport all hosts 0.0.0.0   - Default cadport 5000 - overridden by batch files vpcom1-9.bat

#    group id:  m-med  f-fire  p-police
#            route cad message to med_conn - port 5100,  fir_conn - port 5200,  pol_conn - port 5300    all on localhost 
#                          
#            read messages from ProQA - send all to  i/catchpro.php
 

import socket
import select
import requests
from requests.exceptions import RequestException
import sys
import argparse

# Global constants
endtext = "</comm>"
catchproname = "https://www.brownleedatasystems.com/i/catchpro.php"
timeout = 10

# Define command-line arguments
parser = argparse.ArgumentParser(
    description="Bridge communications between CAD and ProQA"
    )

#-d / --debug
parser.add_argument("-d", "--debug", dest="debug", default=False,
                    action="store_true", help="enable debugging outputs")

#--medhost
parser.add_argument("--medhost", dest="medhost",
                    default="localhost",
                    help="ProQA Med hostname ")
#--medport
parser.add_argument("--medport", dest="medport",
                    default=5100, type=int,
                    help="ProQA Med port")
#--firhost
parser.add_argument("--firhost", dest="firhost",
                    default="localhost",
                    help="ProQA Fire hostname ")
#--firport
parser.add_argument("--firport", dest="firport",
                    default=5200, type=int,
                    help="ProQA Fire port")
                    
#--polhost
parser.add_argument("--polhost", dest="polhost",
                    default="localhost",
                    help="ProQA Police hostname ")
#--polport
parser.add_argument("--polport", dest="polport",
                    default=5300, type=int,
                    help="ProQA Police port")

#--cadhost
parser.add_argument("--cadhost", dest="cadhost",
                    default="0.0.0.0",
                    help="address to listen on for connections from CAD")

#--cadport
parser.add_argument("--cadport", dest="cadport", type=int,
                    default=5000,
                    help="port to listen on for connections from CAD")

#--catchpro
parser.add_argument("-u", "--catchpro", dest="catchpro",
                    default=catchproname,
                    help="URL to POST ProQA messages to")
#parse arguments
options = parser.parse_args()

debug = options.debug

if debug:
    print("Processed command-line arguments:")
    print(options)

medhost = options.medhost
medport = options.medport
firhost = options.firhost
firport = options.firport
polhost = options.polhost
polport = options.polport

cadhost = options.cadhost
cadport = options.cadport
catchpro = options.catchpro

# _________________________________________________________________________________________
#                              proqa connections - medical, fire, police
# _________________________________________________________________________________________


#  connect to medical
try:
    med_conn = socket.create_connection((medhost, medport))
except OSError as e:
    print(f"Failed to connect to ProQA MED on {medhost}:{medport}: {e}")
    sys.exit(1)
    
#  connect to fire                
try:
    fir_conn = socket.create_connection((firhost, firport))
except OSError as e:
    print(f"Failed to connect to ProQA Fire on {firhost}:{firport}: {e}")
    sys.exit(1)
    
#  connect to police
try:
    pol_conn = socket.create_connection((polhost, polport))
except OSError as e:
    print(f"Failed to connect to ProQA Police on {polhost}:{polport}: {e}")
    sys.exit(1)


# _________________________________________________________________________________________
#                          connect to cad    
# _________________________________________________________________________________________

debug and print(f"starting up on {cadhost} port {cadport}")

try:
    # Create a socket, bind to the port, and start listening for connections
    sock = socket.create_server((cadhost, cadport), backlog=1)
    sock_fd = sock.fileno()
except OSError as e:
    print(f"Failed to bind to cad port {cadport}: {e}")
    sys.exit(2)

# _________________________________________________________________________________________
#                Setup rlist of connections:  medical, fire, police, and cad
# _________________________________________________________________________________________

# Wait for a connection
while True:
    debug and print("waiting for a connection or data from:  ProQA Med, Fire, Police  or CAD")
    try:
        # Wait for data to read from either CAD or ProQA
        rlist = select.select([sock_fd, med_conn, fir_conn, pol_conn], [], [])[0]

        # __________________________________________________________________________________
        #   Connection From CAD. Read entire string, route based on leading group id:  m,f,p  - sent from cad3
        # __________________________________________________________________________________
        if sock_fd in rlist:
        
            cad_conn, client_address = sock.accept()
            debug and print(f"New connection from client: {client_address[0]}")

            # Keep reading from client until there's no more to read
            sfulldata=""
 
            fulldata = bytes(sfulldata, 'utf-8')
            while True:
                try:
                    data = cad_conn.recv(16)

                    if data:
                        fulldata+=data
                        
                    # Or see that the client closed the connection
                    else:
                        bgroupid=fulldata[0:1]
                        senddata=fulldata[1:]
                        
                        groupid=bgroupid.decode("utf-8") 

                        debug and print(f"Received full from CAD: {fulldata}")
                        debug and print(f"Groupid: {groupid}")
                        debug and print(f"Senddata: {senddata}")
                        
                        # send to medical
                        if groupid=='m':
                            med_conn.sendall(senddata)
                            
                        # send to fire
                        if groupid=='f':
                            fir_conn.sendall(senddata)
                            
                        # send to police
                        if groupid=='p':
                            pol_conn.sendall(senddata)
                        
                        debug and print("Connection closed by CAD")
                        cad_conn.close()
                        break

                except OSError as e:
                    print(f"Error exchanging communications between CAD and ProQA: {e}")

        # medical - post to cad via catchpro_url
        if med_conn in rlist:
            med_msg = ""

            while True:
                data = med_conn.recv(16)

                if data:
                    debug and print(f"received from ProQA: {data}")
                    med_msg += data.decode('utf-8')

                    # Is this the end of the medical message?
                    if endtext in med_msg:
                        break

                # Or see that the server closed the connection
                else:
                    debug and print("ProQA med has closed the connection")
                    sock.close()
                    sys.exit(3)

            if med_msg:
                debug and print(f"posting med msg to catchpro_url: {med_msg}")
                form_data = {'msg': med_msg}
                try:
                    resp = requests.post(catchpro, data=form_data,
                           timeout=timeout)
                    debug and print(f"HTTP post returned status {resp.status_code}")

                except RequestException as e:
                    debug and print(f"Failed to post to {catchpro_url}: {e}")

        # fire - post to cad via catchpro_url
        if fir_conn in rlist:
            fir_msg = ""

            while True:
                data = fir_conn.recv(16)

                if data:
                    debug and print(f"received from ProQA: {data}")
                    fir_msg += data.decode('utf-8')

                    # Is this the end of the medical message?
                    if endtext in fir_msg:
                        break

                # Or see that the server closed the connection
                else:
                    debug and print("ProQA Fire has closed the connection")
                    sock.close()
                    sys.exit(3)

            if fir_msg:
                debug and print(f"posting fire msg to catchpro_url: {fir_msg}")
                form_data = {'msg': fir_msg}
                try:
                    resp = requests.post(catchpro, data=form_data,
                           timeout=timeout)
                    debug and print(f"HTTP post returned status {resp.status_code}")

                except RequestException as e:
                    debug and print(f"Failed to post to {catchpro_url}: {e}")
                    
        # police - post to cad via catchpro_url
        if pol_conn in rlist:
            pol_msg = ""

            while True:
                data = pol_conn.recv(16)

                if data:
                    debug and print(f"received from ProQA: {data}")
                    pol_msg += data.decode('utf-8')

                    # Is this the end of the police message?
                    if endtext in pol_msg:
                        break

                # Or see that the server closed the connection
                else:
                    debug and print("ProQA Police has closed the connection")
                    sock.close()
                    sys.exit(3)

            if pol_msg:
                debug and print(f"posting police msg to catchpro_url: {pol_msg}")
                form_data = {'msg': pol_msg}
                try:
                    resp = requests.post(catchpro, data=form_data,
                           timeout=timeout)
                    debug and print(f"HTTP post returned status {resp.status_code}")

                except RequestException as e:
                    debug and print(f"Failed to post to {catchpro_url}: {e}")
        
    except KeyboardInterrupt:
        debug and print("Received interrupt signal, exiting")
        break

# Close all connections
sock.close()
med_conn.close()
fir_conn.close()
pol_conn.close() 

debug and print("Connection closed")

sys.exit(0)