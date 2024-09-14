#!/usr/bin/env python3

#  pqaclient.py  compile and run from c:\vproute on each CAD terminal
#    batch file pqa1 - 9.bat  
#        contents of pqa1.bat  "c:\vproute pqaclient -d -o 1"   (for station S1) 

#  connect to:   
#     pqaserver.py  running from rms. /home/brownlee/services
#     proqa  med, fire, police running on localhost
  
#     route cad message to med_conn - port 5100,  fir_conn - port 5200,  pol_conn - port 5300    all on localhost 
#                          

import socket
import select
import requests
from requests.exceptions import RequestException
import sys
import time
import argparse

# Global constants
endtext = "</comm>"
catchproname = "https://www.brownleedatasystems.com/i/catchpro.php"
catchprotimeout = 10

# Define command-line arguments
parser = argparse.ArgumentParser(
    description="Client into pqaserver.py on rms. for communications between CAD and ProQA med,fire,police"
    )

#-d / --debug
parser.add_argument("-d", "--debug", dest="debug", default=False,
                    action="store_true", help="enable debugging outputs")

#-o / --operator-id
parser.add_argument("-o", "--operator-id", dest="operatorid",
                    help="Operator ID to report to pqaserver")

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

#--pqaserverhost
parser.add_argument("--pqaserverhost", dest="pqaserverhost",
                    default="167.71.250.119",
                    help="pqaserver IP")

#--pqaserverport
parser.add_argument("--pqaserverport", dest="pqaserverport", type=int,
                    default=6000,
                    help="Pqaserver port")

#--catchpro
parser.add_argument("-u", "--catchpro", dest="catchpro",
                    default=catchproname,
                    help="URL to POST ProQA messages")
#parse arguments
options = parser.parse_args()

debug = options.debug

if debug:
    print("Processed command-line arguments:")
    print(options)

if not options.operatorid:
    parser.error("Operator ID is required")

operator_id = options.operatorid

medhost = options.medhost
medport = options.medport
firhost = options.firhost
firport = options.firport
polhost = options.polhost
polport = options.polport

pqaserverhost = options.pqaserverhost
pqaserverport = options.pqaserverport
catchpro = options.catchpro

# _________________________________________________________________________________________
#                              proqa connections - medical, fire, police
# _________________________________________________________________________________________


#  connect to medical, fire, police 
try:
    med_conn = socket.create_connection((medhost, medport))
except OSError as e:
    print(f"Failed to connect to ProQA MED on {medhost}:{medport}: {e}")
    sys.exit(1)

try:
    fir_conn = socket.create_connection((firhost, firport))
except OSError as e:
    print(f"Failed to connect to ProQA Fire on {firhost}:{firport}: {e}")
    sys.exit(1)

try:
    pol_conn = socket.create_connection((polhost, polport))
except OSError as e:
    print(f"Failed to connect to ProQA Police on {polhost}:{polport}: {e}")
    sys.exit(1)
    
# Create empty buffers for receiving messages
pqaserver_msg = "".encode('utf-8')
med_msg = ""
fir_msg = ""
pol_msg = ""

# set exit code to return to OS on normal exit
exit_code=0

# Wait for a connection
pqaserver_conn = None

while True:
# _________________________________________________________________________________________
#                          connect to pqaserver if not connected
# _________________________________________________________________________________________

    try:
        if not pqaserver_conn:
            # In case this is a reconnect and we lost connection after a
            # partial message, clear the buffer
            pqaserver_msg = "".encode('utf-8')
            print(f"Connecting to pqaserver on {pqaserverhost}:{pqaserverport}...")

        while not pqaserver_conn:
            try:
                pqaserver_conn = socket.create_connection((pqaserverhost, pqaserverport), timeout=5)

                # Keep connection from blocking indefinitely
                pqaserver_conn.settimeout(1)

                # Identify ourselves
                pqaserver_conn.sendall(operator_id.encode('utf-8'))

                # Make sure server acknowledged us
                data = pqaserver_conn.recv(32)

                if not data:
                    raise socket.error("pqaserver answered but didn't respond")
                elif data.decode('utf-8').rstrip() != "OK":
                    raise socket.error(f"Pqaserver replied: {data.decode('utf-8').rstrip()}")
                else:
                    print("Connection to pqaserver succeeded, entering normal operation")
            except OSError as e:
                print(f"Unable to connect to pqaserver: {e}")

                if pqaserver_conn:
                    pqaserver_conn.shutdown(socket.SHUT_RDWR)
                    pqaserver_conn.close()
                    pqaserver_conn = None

                print("Retrying...")
                time.sleep(5)
    
        debug and print("waiting for a connection or data from:  ProQA Med, Fire, Police  or pqaserver / CAD")
        # Wait for data to read from either pqaserver or ProQA med,fir,or police
        rlist = select.select([pqaserver_conn, med_conn, fir_conn, pol_conn], [], [])[0]

        # __________________________________________________________________________________
        #   Connection From pqaserver. Read entire string, route based on leading group id:  m,f,p  - sent from cad3
        # __________________________________________________________________________________
        if pqaserver_conn in rlist:
            try:
                data = pqaserver_conn.recv(16)

                if data:
                    pqaserver_msg+=data
                    debug and print(f"Received from pqaserver: {data}")

                    # Did we receive the message terminator?
                    if endtext in pqaserver_msg.decode('utf-8'):
                        # Parse out group ID in first char from rest of message
                        groupid=pqaserver_msg[0:1].decode("utf-8") 
                        senddata=pqaserver_msg[1:]

                        debug and print(f"Received full from CAD: {pqaserver_msg}")
                        debug and print(f"Groupid: {groupid}")
                        debug and print(f"Senddata: {senddata}")
                    
                        # Clear the buffer
                        pqaserver_msg = "".encode('utf-8')
                    
                        # send to medical
                        if groupid=='m':
                            try:
                                med_conn.sendall(senddata)
                            except OSError as e:
                                debug and print(f"Error sending to ProQA Medical: {e}")
                                pqaserver_conn.sendall("NO\n".encode('utf-8'))
                                exit_code=3
                                break

                            pqaserver_conn.sendall("OK\n".encode('utf-8'))

                        # send to fire
                        if groupid=='f':
                            try:
                                fir_conn.sendall(senddata)
                            except OSError as e:
                                debug and print(f"Error sending to ProQA Fire: {e}")
                                pqaserver_conn.sendall("NO\n".encode('utf-8'))
                                exit_code=3
                                break

                            pqaserver_conn.sendall("OK\n".encode('utf-8'))

                        # send to police
                        if groupid=='p':
                            try:
                                pol_conn.sendall(senddata)
                            except OSError as e:
                                debug and print(f"Error sending to ProQA Police: {e}")
                                pqaserver_conn.sendall("NO\n".encode('utf-8'))
                                exit_code=3
                                break

                            pqaserver_conn.sendall("OK\n".encode('utf-8'))
                        else:
                            pqaserver_conn.sendall("NO\n".encode('utf-8'))
                    
                # Or see that the client closed the connection
                else:
                    raise socket.error("Lost connection to pqaserver, attempting reconnect")
                    continue

            except OSError as e:
                print(f"Error receiving data from pqaserver: {e}")
                print("Attempting to reconnect to pqaserver")
                pqaserver_conn.shutdown(socket.SHUT_RDWR)
                pqaserver_conn.close()
                pqaserver_conn = None
                continue

        # medical - post to cad via catchpro_url
        if med_conn in rlist:
            data = med_conn.recv(16)

            if data:
                debug and print(f"received from ProQA Med: {data}")
                med_msg += data.decode('utf-8')

                # Is this the end of the medical message?
                if endtext in med_msg:
                    debug and print(f"posting med msg to catchpro_url: {med_msg}")

                    # Get the form post ready
                    form_data = {'msg': med_msg}

                    # Clear the buffer
                    med_msg = ""

                    # Post the form data to catchpro
                    try:
                        resp = requests.post(catchpro, data=form_data,
                               timeout=catchprotimeout)
                        debug and print(f"HTTP post returned status {resp.status_code}")

                    except RequestException as e:
                        debug and print(f"Failed to post to {catchpro_url}: {e}")

            # Or see that the server closed the connection
            else:
                debug and print("ProQA med has closed the connection")
                exit_code=3
                break

        # fire - post to cad via catchpro_url
        if fir_conn in rlist:
            data = fir_conn.recv(16)

            if data:
                debug and print(f"received from ProQA Fire: {data}")
                fir_msg += data.decode('utf-8')

                # Is this the end of the fire message?
                if endtext in fir_msg:
                    debug and print(f"posting fire msg to catchpro_url: {fir_msg}")

                    # Get the form post ready
                    form_data = {'msg': fir_msg}

                    # Clear the buffer
                    fir_msg = ""

                    # Post the form data to catchpro
                    try:
                        resp = requests.post(catchpro, data=form_data,
                               timeout=catchprotimeout)
                        debug and print(f"HTTP post returned status {resp.status_code}")

                    except RequestException as e:
                        debug and print(f"Failed to post to {catchpro_url}: {e}")

            # Or see that the server closed the connection
            else:
                debug and print("ProQA fire has closed the connection")
                exit_code=3
                break

        # police - post to cad via catchpro_url
        if pol_conn in rlist:
            data = med_conn.recv(16)

            if data:
                debug and print(f"received from ProQA Police: {data}")
                pol_msg += data.decode('utf-8')

                # Is this the end of the police message?
                if endtext in pol_msg:
                    debug and print(f"posting police msg to catchpro_url: {pol_msg}")

                    # Get the form post ready
                    form_data = {'msg': pol_msg}

                    # Clear the buffer
                    pol_msg = ""

                    # Post the form data to catchpro
                    try:
                        resp = requests.post(catchpro, data=form_data,
                               timeout=catchprotimeout)
                        debug and print(f"HTTP post returned status {resp.status_code}")

                    except RequestException as e:
                        debug and print(f"Failed to post to {catchpro_url}: {e}")

            # Or see that the server closed the connection
            else:
                debug and print("ProQA police has closed the connection")
                exit_code=3
                break

    except KeyboardInterrupt:
        debug and print("Received interrupt signal, exiting")
        break

# Close all connections
for f in [pqaserver_conn,med_conn,fir_conn,pol_conn]:
    if f:
        f.close()

debug and print("Connection closed")

sys.exit(exit_code)
