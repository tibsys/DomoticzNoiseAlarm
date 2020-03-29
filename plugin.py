#
# coding=utf-8
# Plugin: Noise Alarm plugin
# Developer: Tristan Israël - Alefbet
#
"""
<plugin key="NoiseAlarm" name="Noise Alarm" author="alefbet" version="1.0.7" wikilink="" externallink="https://alefbet.net/">
    <description>
        <h2>Noise Alarm</h2><br/>
        <h3>Features</h3>
        <ul style="list-style-type:square">
            <li>A remplir</li>            
        </ul>
        <h3>Devices</h3>
        <ul style="list-style-type:square">
            <li>A remplir</li>            
        </ul>
    </description>
    <params>        
        <param field="Address" label="IP Address" width="200px" required="true" default="127.0.0.1"/>
        <param field="Port" label="Port" width="200px" required="true" default="80"/>
        <param field="Username" label="Login" width="200px" required="false" default=""/>
        <param field="Password" label="Password" width="200px" required="false" default=""/>
        <param field="Mode1" label="Audio stream path" width="200px" required="true" default="/audio.wav"/>
        <param field="Mode2" label="Audio sample frequency (hz)" width="200px" required="true" default="8000"/>        
        <param field="Mode3" label="Noise threshold (dB)" width="200px" required="true" default="30"/>
        <param field="Mode4" label="Low-pass cut frequency (0=disabled)" width="200px" required="true" default="0"/>
        
        <param field="Mode6" label="Debug" width="75px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal" default="true" />
            </options>
        </param>
    </params>
</plugin>
"""

import sys
import math
import audioop
import socket
import io
import base64
import re
import time
import struct
import numpy
from scipy.signal import butter, lfilter
import scipy.signal as sg
from collections import deque
import Domoticz

class BasePlugin:
    inSock = None
    heartbeatFreq = 1
    length = 0    
    isReady = False # Connected and initialized
    isAlive = False # Heartbeat
    currentValue = False
    isStarted = False # Plugin started
    readErrors = 0
    headersReceived = False
    filterEnabled = False
    filterFrequency = 100
    sampleFrequency = 8000
    lowpass = 100
    dbValues = deque([1,1,1,1,1])
    
    def __init__(self):   
        self.isAlive = False       

    def createDevices(self):
        if not 1 in Devices:
            Domoticz.Device(Name="Status",  Unit=1, Type=244, Subtype=62, Switchtype=0, Used=1).Create()            
            Domoticz.Log("Created device " + Devices[1].Name)
            if not 1 in Devices:
                Domoticz.Log("Device could not be created")
                return False

        if not 2 in Devices:
            Domoticz.Device(Name="Noise level", Unit=2, TypeName="Custom", Options={"Custom": "1;dB"}, Used=1).Create()
            Domoticz.Log("Created device " + Devices[2].Name)
            if not 2 in Devices:
                Domoticz.Log("Device could not be created")
                return False

        if not 3 in Devices:
            Domoticz.Device(Name="Connection status", Unit=3, Type=244, Subtype=62, Switchtype=0, Used=1).Create()            
            Domoticz.Log("Created device " + Devices[3].Name)
            if not 3 in Devices:
                Domoticz.Log("Device could not be created")
                return False

        return True

    def connectToHost(self):
        Domoticz.Debug("Try to connect to webcam")
        self.headersReceived = False        

        self.inSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.inSock.connect((Parameters["Address"], int(Parameters["Port"])))
            Domoticz.Debug("Connection to the webcam OK")
        except:
            Domoticz.Debug("Connection to the webcam refused")
            self.isReady = False
            return False
        
        Domoticz.Debug("Querying audio stream")

        username = Parameters["Username"]        

        #TODO: check if Mode1 starts with '/'
        connString = "GET " +Parameters["Mode1"] +" HTTP/1.0\r\nHost: " +Parameters["Address"]  +"\r\n"

        if not username:
            Domoticz.Debug("Using anonymous connection")
        else:
            password = Parameters["Password"]
            #Domoticz.Debug("Using credentials: " +username +":" +password)               
            Domoticz.Debug("Using credentials")
            data = bytearray(username +":" +password, "utf-8")
            token=base64.encodebytes(data)
            connString += ("Authorization: Basic " +token.decode("utf-8") +"\r\n")

        # Terminate GET request string
        connString += "\r\n"

        #Domoticz.Debug("Connection string: " +connString)

        try:
            b = bytearray()
            b.extend(map(ord, connString))
            self.inSock.send(b)            
        except BrokenPipeError:
            Domoticz.Debug("Connection to the webcam interrupted")
            return False
                
        self.readErrors = 0        

        # Get headers
        s = self.inSock.recv( 1024 )
        cnt = 0
        self.headersReceived = False

        while not s.startswith(b"RIFF") and cnt < 10:
            Domoticz.Debug("Receiving HTTP headers")                
            cnt = cnt + 1
            s = self.inSock.recv( 1024 )

        if s.startswith(b"RIFF"):
            Domoticz.Debug("Start receiving the audio")
            self.headersReceived = True     
            self.isReady = True
            Devices[3].Update(nValue=1, sValue="On")
            return True          
        else:
            Domoticz.Debug("Did not receive the headers... Retry next time.")
            self.isReady = False
            self.inSock.close()
            Domoticz.Debug("Connection closed")
            return False

        return True

    def onStart(self):
        # Check Debug setting
        if Parameters["Mode6"] == "Debug":
            Domoticz.Debugging(1)
            DumpConfigToLog()

        Domoticz.Heartbeat(3)

        # Set Nyquist frequency for low pass filter
        self.filterEnabled = False
        self.filterFrequency = int(Parameters["Mode4"])
        if self.filterFrequency > 0:            
            Domoticz.Log("Activated Lowpass filter with frequency " +str(self.filterFrequency))
            self.sampleFrequency = int(Parameters["Mode2"])
            if self.sampleFrequency == 0:
                Domoticz.Log("Sample frequency not well formatted. Falling back to 8000.")
                self.sampleFrequency = 8000
            nyq = 0.5 * self.sampleFrequency           
            self.lowpass = self.filterFrequency / nyq
            self.filterEnabled = True
               
        if self.createDevices():
            Domoticz.Debug("Opening the audio stream on the device")                                            
            self.canContinue = True

        self.isStarted = True

        # Set initial devices values
        Devices[1].Update(nValue=0, sValue="Off")
        Devices[2].Update(nValue=0, sValue="0")
        Devices[3].Update(nValue=0, sValue="Off")

        if self.connectToHost():
            if self.isReady:
                self.readAudio()

    def applyFilter(self, sample):
        Domoticz.Debug("Applying filter")

        # Unpack wave
        wav = self.unpack_wave(sample)

        # Convert to floats        
        floats = self.wave_shorts_to_floats(wav)
        
        # Apply filter
        b, a = sg.butter(4, self.lowpass, 'low')
        filteredSignal = lfilter(b, a, floats) 

        # Convert to ints
        ints = self.floats_to_wave_ints(filteredSignal)

        # Pack wave
        return self.pack_wave(ints)

    def readAudio(self):
        if not self.headersReceived:
            Domoticz.Debug("HTTP headers not received. Cannot read the audio")
            self.inSock.close()
            return False

        if self.isStarted:
            inputSignal = self.inSock.recv( 300000 )                        
            
            Domoticz.Debug("Received " +str(len(inputSignal)) +" bytes of audio")
            if len(inputSignal) > 0:
                if self.filterEnabled:
                    audioSignal = self.applyFilter(inputSignal)
                else:
                    audioSignal = inputSignal

                rms = audioop.rms(audioSignal, 2)
                dB = self.toDecibel(rms)                
                Domoticz.Debug("Current dB value=" + str(dB))                

                dbAvg = self.addToDecibelsAndReturnAverage(dB)
                Domoticz.Debug("Average dB values=" + str(dbAvg))

                Devices[2].Update(nValue=dbAvg, sValue=str(dbAvg))
                Devices[1].Touch()

                if dbAvg > int(Parameters["Mode3"]):                                        
                    if self.currentValue != True:
                        Domoticz.Log("Switch to On")
                        Devices[1].Update(nValue=1, sValue="On")
                        self.currentValue = True
                else:
                    if self.currentValue != False:
                        Domoticz.Log("Switch to Off")
                        Devices[1].Update(nValue=0, sValue="Off")
                        self.currentValue = False
            else:
                Domoticz.Debug("No data received from webcam. Connection error?")
                self.readErrors = self.readErrors + 1
                if self.readErrors >= 3:
                    Domoticz.Log("To many read errors. Disconnecting from webcam.")
                    self.inSock.close()
                    self.isReady = False   
                    Devices[3].Update(nValue=0, sValue="Off")                         
            
            #time.sleep(0) # Yield
        else:
            Domoticz.Debug("Plugin not started or stopping")
            
    def onStop(self):
        Domoticz.Debug("onStop called") 
        Devices[3].Update(nValue=0, sValue="Off")  

        self.isReady = False
        self.isStarted = False
           
        if self.inSock:
            self.inSock.close()                                           

    def onConnect(self, Connection, Status, Description):
        Domoticz.Debug("onConnect called")
        
    def onMessage(self, Data, Status, Extra):
        Domoticz.Debug("onMessage called")

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Debug("onCommand called")        

    def onDisconnect(self, Connection):
        Domoticz.Debug("onDisconnect called for connection to: "+Connection.Address+":"+Connection.Port)

    def onHeartbeat(self):
        self.isAlive = True

        if not self.isStarted:
            return False

        if not self.isReady:                    
            Domoticz.Debug("Try to reconnect to the webcam")
            self.connectToHost()
        
        if self.isReady:
            self.readAudio()

    def toDecibel(self, rms):
        return round((20*(math.log(rms) / math.log(10))))

    def addToDecibelsAndReturnAverage(self, db):
        self.dbValues.appendleft(db)
        self.dbValues.pop()
        return int(round(numpy.mean(self.dbValues)))

    def unpack_wave(self, data):
        dlen=(len(data)/2)
        return struct.unpack('%ih' % dlen, data)

    def wave_shorts_to_floats(self, ints):
        return [i * 1.0/32768 for i in ints]

    def floats_to_wave_ints(self, floats):
        return [int(round(f * 32767)) for f in floats]

    def pack_wave(self, data):
        dlen=len(data)
        return struct.pack('<%dh' % dlen, *data)

global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Data, Status, Extra):
    global _plugin
    _plugin.onMessage(Data, Status, Extra)

def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

# Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
    return