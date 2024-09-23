#!/usr/bin/env python3

# pqclient - compile for windows .exe   run from batch files  pq1-9.bat
# 

#   pq1.bat     c:\vproute\pqclient -o 1

# Files in c:\vproute on all TC computers:   pqclient.exe   pq1.bat thru pq9.bat

import socket
import select
import requests
from requests.exceptions import RequestException
import sys
import time
import argparse

# Globals
version='1.0'
eomstring = "</comm>"
exit_code=0

# Defaults for command-line args
debug = True 
catchname = "https://work.brownleedatasystems.com/i/pqcatchlog.php"
catchtimeout = 10
medhost = 'localhost'
medport = 5100
firhost = 'localhost'
firport = 5200
polhost = 'localhost'
polport = 5300
serverhost = '167.71.250.119'  #rms. server
serverport = 6000

# Exceptions to throw
class proqaexception(Exception):
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

    parser = argparse.ArgumentParser(
        description="Client into pqserver.py on rms. for communications between CAD and ProQA med,fire,police"
        )

    #-d / --debug
    parser.add_argument("-d", "--debug", dest="debug", default=debug,
                        action="store_true", help="enable debugging outputs")

    #-o / --operator-id
    parser.add_argument("-o", "--operator-id", dest="operatorid",
                        help="Operator ID to report to pqaserver")
                        
    #--medhost
    parser.add_argument("--medhost", dest="medhost",
                        default=medhost,
                        help="ProQA Med hostname ")

    #--medport
    parser.add_argument("--medport", dest="medport",
                        default=medport, type=int,
                        help="ProQA Med port")

    #--firhost
    parser.add_argument("--firhost", dest="firhost",
                        default=firhost,
                        help="ProQA Fire hostname ")

    #--firport
    parser.add_argument("--firport", dest="firport",
                        default=firport, type=int,
                        help="ProQA Fire port")
                        
    #--polhost
    parser.add_argument("--polhost", dest="polhost",
                        default=polhost,
                        help="ProQA Police hostname ")

    #--polport
    parser.add_argument("--polport", dest="polport",
                        default=polport, type=int,
                        help="ProQA Police port")

    #--serverhost
    parser.add_argument("--serverhost", dest="serverhost",
                        default=serverhost,
                        help="pqserver IP or hostname")

    #--serverport
    parser.add_argument("--serverport", dest="serverport", type=int,
                        default=serverport,
                        help="Pqserver port")

    #--catchname
    parser.add_argument("-u", "--catchname", dest="catchname",
                        default=catchname,
                        help="URL to POST ProQA messages")

    #parse arguments
    options = parser.parse_args()

    # Set global debug setting from command-line options
    debug = options.debug

    if debug:
        print("Processed command-line arguments:")
        print(options)

    # Required argument
    if not options.operatorid:
        parser.error("Operator ID is required")

    return options

def proqaconnect(name, host, port):
    """proqaconnect() -- Make connection to specified ProQA application

    Params:
    name -- human-friendly name of the application
    host -- hostname or IP where application is listening
    port -- TCP port number where application is listening

    Throws:
    proqaexception when connection can't be established with ProQA application

    Returns:
    File descriptor of connected TCP socket
    """

    try:
        return socket.create_connection((host, port))
    except OSError as e:
        raise proqaexception(f"Failed to connect to ProQA {name} on {host}:{port}: {e}")

def proqasend(conn, msg):
    """proqasend() -- Send message to a ProQA application and respond with results

    Params:
    conn -- file descriptor of the TCP socket to send to
    msg -- string to send
    name -- human-friendly name of the application
    host -- hostname or IP where application is listening
    port -- TCP port number where application is listening

    Throws:
    proqaexception when communication fails with ProQA application

    Returns:
    None
    """

    try:
        conn.sendall(msg)
        print(f"Data successfully sent to ProQA {name}")
    except OSError as e:
        raise proqaexception(f"Error sending to ProQA {name}: {e}")

    return True

def serverconnect(host, port, operatorid):
    """serverconnect() -- Keep retrying until connection can be made to PQServer

    Params:
    host -- hostname or IP where PQServer is listening
    port -- TCP port number where PQServer is listening
    operatorid -- numeric operator identifier

    Throws:
    None

    Returns:
    File descriptor of connected TCP socket
    """

    conn = None

    while not conn:
        try:
            conn = socket.create_connection((host, port), timeout=5)
            conn.settimeout(1)
            conn.sendall(operatorid.encode('utf-8'))
            data = conn.recv(32)

            if not data:
                raise socket.error("pqserver answered but didn't respond")
            elif data.decode('utf-8').rstrip() != "OK":
                raise socket.error(f"pqserver replied: {data.decode('utf-8').rstrip()}")
            else:
                print("Connection to pqserver succeeded, entering normal operation")
        except OSError as e:
            print(f"Unable to connect to pqserver: {e}")
            if conn:
                conn.shutdown(socket.SHUT_RDWR)
                conn.close()
                conn = None

            print("Retrying...")
            time.sleep(5)

    # Connection established
    return conn

def catchpost(name, url, msg):
    """catchpost() -- Post message to catch URL

    Params:
    name -- human-friendly name of application where message originated
    url -- URL where message should be sent
    msg -- message to post

    Throws:
    None

    Returns:
    True on successful post, False otherwise
    """

    formdata = {'msg': msg}

    try:
        resp = requests.post(url, data=formdata, timeout=catchtimeout)
        debug and print(f"HTTP post returned status {resp.status_code}")

    except RequestException as e:
        debug and print(f"Failed to post {name} to {url}: {e}")
        return False

    return True

def closeall(connections):
    """closeall() -- Close all connections in the supplied list

    Params:
    connections -- list of connections to try to close

    Throws:
    None

    Returns:
    None
    """

    for c in connections:
        if c:
            c.close()
    debug and print("Connections closed")

if __name__ == "__main__":
    options = parsecmdline()

    print(f"Pqclient - Version {version}  Station# {options.operatorid}")
    print()

    # _________________________________________________________________________________________
    #                              proqa connections - medical, fire, police
    # _________________________________________________________________________________________
    medcon = None
    fircon = None
    polcon = None
    servercon = None

    # Create empty buffers for receiving messages
    servermsg = "".encode('utf-8')
    medmsg = ""
    firmsg = ""
    polmsg = ""

    try:
        #  connect to medical, fire, police 
        medcon = proqaconnect("Med", options.medhost, options.medport)
        fircon = proqaconnect("Fire", options.firhost, options.firport)
        polcon = proqaconnect("Police", options.polhost, options.polport)

        # Wait for a connection
        while True:
            # _________________________________________________________________________________________
            #                          connect to pqserver if not connected
            # _________________________________________________________________________________________
            if not servercon:
                # In case this is a reconnect and we lost connection after a
                # partial message, clear the buffer
                servermsg = "".encode('utf-8')
                print(f"Connecting to pqserver on {options.serverhost}:{options.serverport}...")
                servercon = serverconnect(options.serverhost, options.serverport, options.operatorid)

            debug and print("Waiting for data from:  ProQA Med, Fire, Police  or pqserver/CAD")
            # Wait for data to read from either pqserver or ProQA med,fir,or police
            rlist = select.select([servercon, medcon, fircon, polcon], [], [])[0]

            # __________________________________________________________________________________
            #   Connection From pqserver. Read entire string, route based on leading group id:  m,f,p  - sent from cad3
            # __________________________________________________________________________________
            if servercon in rlist:
                try:
                    data = servercon.recv(16)
                    if data:
                        servermsg+=data
                        debug and print(f"Received from pqserver: {data}")

                        # Did we receive the message terminator?
                        if eomstring in servermsg.decode('utf-8'):
                            # read one more batch
                            data = servercon.recv(16)
                            if data:
                                servermsg+=data
                                debug and print(f"Received last from pqserver: {data}")
                                debug and print()
                           
                            # Parse out group ID in first char from rest of message
                            groupid=servermsg[0:1].decode("utf-8") 
                            senddata=servermsg[1:]

                            print(f"Received full from CAD: {servermsg}")
                            print()
                            print(f"Groupid: {groupid}")
                            print(f"Senddata: {senddata}")
                            print()
                            
                            # Clear the buffer
                            servermsg = "".encode('utf-8')
                        
                            # Figure out where this is going
                            name = None
                            conn = None

                            if groupid=='m':
                                name = "Med"
                                conn = medcon
                            elif groupid=='f':
                                name = "Fire"
                                conn = fircon
                            elif groupid=='p':
                                name = "Police"
                                conn = polcon
                        
                            # If group ID was valid, send message
                            if name:
                                try:
                                    proqasend(name, conn, senddata)
                                except proqaexception as e:
                                    servercon.sendall("NO\n".encode('utf-8'))
                                    raise proqaexception(e)

                                servercon.sendall("OK\n".encode('utf-8'))
                            else:
                                # Invalid group ID
                                servercon.sendall("NO\n".encode('utf-8'))

                    # Or see that the client closed the connection
                    else:
                        raise socket.error("Lost connection to pqserver, attempting reconnect")

                except OSError as e:
                    print(f"Error receiving data from pqserver: {e}")
                    print("Attempting to reconnect to server")
                    servercon.shutdown(socket.SHUT_RDWR)
                    servercon.close()
                    servercon = None
                    continue

            # medical - post to cad via catchpro_url
            if medcon in rlist:
                data = medcon.recv(16)
                if data:
                    debug and print(f"received from ProQA Med: {data}")
                    medmsg += data.decode('utf-8')
                    if eomstring in medmsg:
                        print(f"posting med msg to catchname: {medmsg}")
                        catchpost("Medical", options.catchname, medmsg)
                        medmsg = ""
                # Or see that the server closed the connection
                else:
                    raise proqaexception("ProQA med has closed the connection")
                
            # fire - post to cad via catchpro_url
            if fircon in rlist:
                data = fircon.recv(16)
                if data:
                    debug and print(f"received from ProQA Fire: {data}")
                    firmsg += data.decode('utf-8')
                    if eomstring in firmsg:
                        print(f"posting fire msg to catchname: {firmsg}")
                        catchpost("Fire", options.catchname, firmsg)
                        firmsg = ""

                # Or see that the server closed the connection
                else:
                    raise proqaexception("ProQA fire has closed the connection")

            # police - post to cad via catchpro_url
            if polcon in rlist:
                data = polcon.recv(16)
                if data:
                    debug and print(f"received from ProQA Police: {data}")
                    polmsg += data.decode('utf-8')
                    if eomstring in polmsg:
                        print(f"posting police msg to catchpro_url: {polmsg}")
                        catchpost("Police", options.catchname, polmsg)
                        polmsg = ""

                # Or see that the server closed the connection
                else:
                    raise proqaexception("ProQA police has closed the connection")

    except proqaexception as e:
        debug and print(f"Exiting: {e}")
        sys.exit(2)

    except KeyboardInterrupt:
        debug and print("Received interrupt signal, exiting")
        sys.exit(0)
    # This runs before the above exceptions always
    finally:
        # Close all connections
        closeall([servercon,medcon,fircon,polcon])
