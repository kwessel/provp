#!/usr/bin/env python3

#  vpcom - read from cad3 on cadport all hosts 0.0.0.0   - Default cadport 5000 - overridden by batch files vpcom1-9.bat

#    group id:  m-med  f-fire  p-police
#            route cad message to med_conn - port 5100,  fir_conn - port 5200,  pol_conn - port 5300    all on localhost 
#                          
#            read messages from ProQA - send all to  i/catchpro.php
 

#                           CONNECT WITH MEDICAL ONLY            

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
    description="Bridge communications between CAD and ProQA"
    )

#-d / --debug
parser.add_argument("-d", "--debug", dest="debug", default=False,
                    action="store_true", help="enable debugging outputs")

#-o / --operator-id
parser.add_argument("-o", "--operator-id", dest="operatorid",
                    help="Operator ID to report to VPCom server")

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

#--vpserverhost
parser.add_argument("--vpserverhost", dest="vpserverhost",
                    default="www.brownleedatasystems.com",
                    help="VPCom server host or IP")

#--vpserverport
parser.add_argument("--vpserverport", dest="vpserverport", type=int,
                    default=5000,
                    help="VPCom server port")

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

if not options.operatorid:
    parser.error("Operator ID is required")

operator_id = options.operatorid

medhost = options.medhost
medport = options.medport
firhost = options.firhost
firport = options.firport
polhost = options.polhost
polport = options.polport

vpserverhost = options.vpserverhost
vpserverport = options.vpserverport
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
    
# _________________________________________________________________________________________
#                Setup rlist of connections:  medical, fire, police, and cad
# _________________________________________________________________________________________

# Wait for a connection
vpserver_conn = None

while True:
# _________________________________________________________________________________________
#                          connect to VPCom server if not connected
# _________________________________________________________________________________________

    try:
        if not vpserver_conn:
            print(f"Connecting to VPCom server on {vpserverhost}:{vpserverport}...")

        while not vpserver_conn:
            try:
                vpserver_conn = socket.create_connection((vpserverhost, vpserverport), timeout=5)

                # Keep connection from blocking indefinitely
                vpserver_conn.settimeout(1)

                # Identify ourselves
                vpserver_conn.sendall(operator_id.encode('utf-8'))

                # Make sure server acknowledged us
                data = vpserver_conn.recv(32)

                if not data:
                    raise socket.error("Server answered but didn't respond")
                elif data.decode('utf-8').rstrip() != "OK":
                    raise socket.error(f"Server replied: {data.decode('utf-8').rstrip()}")
                else:
                    print("Connection succeeded, entering normal operation")
            except OSError as e:
                print(f"Unable to connect to VPCom server: {e}")

                if vpserver_conn:
                    vpserver_conn.shutdown(socket.SHUT_RDWR)
                    vpserver_conn.close()
                    vpserver_conn = None

                print("Retrying...")
                time.sleep(5)
    
        debug and print("waiting for a connection or data from:  ProQA Med, Fire, Police  or CAD")
        # Wait for data to read from either VPCom server or ProQA
        rlist = select.select([vpserver_conn, med_conn], [], [])[0]

        # __________________________________________________________________________________
        #   Connection From VPCom server. Read entire string, route based on leading group id:  m,f,p  - sent from cad3
        # __________________________________________________________________________________
        if vpserver_conn in rlist:
            # Keep reading from client until there's no more to read
            fulldata = "".encode('utf-8')
            while True:
                try:
                    data = vpserver_conn.recv(16)

                    if data:
                        fulldata+=data
                        debug and print(f"Received from VPCom server: {data}")

                        # Did we receive the message terminator?
                        if endtext in fulldata.decode('utf-8'):
                            groupid=fulldata[0:1].decode("utf-8") 
                            senddata=fulldata[1:]
                        
                            debug and print(f"Received full from CAD: {fulldata}")
                            debug and print(f"Groupid: {groupid}")
                            debug and print(f"Senddata: {senddata}")
                        
                            # send to medical
                            if groupid=='m':
                                try:
                                    med_conn.sendall(senddata)
                                except OSError as e:
                                    debug and print(f"Error sending to ProQA Medical: {e}")
                                    vpserver_conn.sendall("NO\n".encode('utf-8'))
                                    break

                                vpserver_conn.sendall("OK\n".encode('utf-8'))

                            # Fire and police go here

                            else:
                                vpserver_conn.sendall("NO\n".encode('utf-8'))
                            break
                        
                    # Or see that the client closed the connection
                    else:
                        raise socket.error("Lost connection to VPCom server, attempting reconnect")


                except OSError as e:
                    print(f"Error receiving data from VPCom server: {e}")
                    print("Attempting to reconnect to VPCom server")
                    vpserver_conn.shutdown(socket.SHUT_RDWR)
                    vpserver_conn.close()
                    vpserver_conn = None
                    break

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
                    vpserver_conn.shutdown(socket.SHUT_RDWR)
                    vpserver_conn.close()
                    sys.exit(3)

            if med_msg:
                debug and print(f"posting med msg to catchpro_url: {med_msg}")
                form_data = {'msg': med_msg}
                try:
                    resp = requests.post(catchpro, data=form_data,
                           timeout=catchprotimeout)
                    debug and print(f"HTTP post returned status {resp.status_code}")

                except RequestException as e:
                    debug and print(f"Failed to post to {catchpro_url}: {e}")

        
    except KeyboardInterrupt:
        debug and print("Received interrupt signal, exiting")
        break

# Close all connections
for f in [vpserver_conn,med_conn]:
    if f:
        f.close()

debug and print("Connection closed")

sys.exit(0)
