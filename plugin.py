#
# coding=utf-8
# Plugin: Noise Alarm plugin
# Developer: Tristan Israël - Alefbet
#
"""
<plugin key="NoiseAlarm" name="Noise Alarm" author="alefbet" version="1.0.5" wikilink="" externallink="https://alefbet.net/">
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
        <param field="Mode1" label="Audio stream path" width="200px" required="true" default="/audio.wav"/>
        <param field="Mode2" label="Listening frequency (seconds)" width="200px" required="true" default="1"/>        
        <param field="Mode3" label="Noise threshold (dB)" width="200px" required="true" default="30"/>
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
    
    def __init__(self):   
        isAlive = False       

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
        self.inSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.inSock.connect((Parameters["Address"], int(Parameters["Port"])))
            Domoticz.Debug("Connection to the webcam OK")
        except ConnectionRefusedError:
            Domoticz.Debug("Connection to the webcam refused")
            self.isReady = False
            return False
        
        Domoticz.Debug("Querying audio stream")
        #TODO: check if Mode1 starts with '/'
        connString = "GET " +Parameters["Mode1"] +" HTTP/1.0\r\nHost: " +Parameters["Address"] +"\r\n\r\n"
        b = bytearray()
        b.extend(map(ord, connString))
        try:
            self.inSock.send(b)            
        except BrokenPipeError:
            Domoticz.Debug("Connection to the webcam interrupted")
            return False
                
        self.readErrors = 0
        self.isReady = True
        Devices[3].Update(nValue=1, sValue="On")

        return True

    def onStart(self):
        # Check heartbeat setting
        if Parameters["Mode2"] != "":
            self.heartbeatFreq = int(Parameters["Mode2"])
        Domoticz.Heartbeat(self.heartbeatFreq)

        # Check Debug setting
        if Parameters["Mode6"] == "Debug":
            Domoticz.Debugging(1)
            DumpConfigToLog()
               
        if self.createDevices():
            Domoticz.Debug("Opening the audio stream on the device")                                            
            self.canContinue = True

        self.isStarted = True

        # Set initial devices values
        Devices[1].Update(nValue=0, sValue="Off")
        Devices[2].Update(nValue=0, sValue="0")
        Devices[3].Update(nValue=0, sValue="Off")

        if(self.connectToHost()):            
            # Do a first read
            self.readAudio()

    def readAudio(self):
        if self.isStarted == True:                            
            s = self.inSock.recv( 300000 )
            #s_ = s.decode()
            if s.startswith(b"HTTP/1.1 200 OK"):
                Domoticz.Debug("Received HTTP header")
                return

            Domoticz.Debug("Received " +str(len(s)) +" bytes")
            if len(s) > 0:
                rms = audioop.rms(s, 2)
                dB = self.toDecibel(rms)                
                Domoticz.Debug("Current dB value=" + str(dB))
                Devices[2].Update(nValue=dB, sValue=str(dB))

                if dB > int(Parameters["Mode3"]):                                        
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
        else:
            Domoticz.Debug("Plugin not started")     
            
    def onStop(self):
        Domoticz.Debug("onStop called")                     
        self.isStarted = False

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

        if not self.isReady:                    
            Domoticz.Debug("Try to reconnect to the webcam")
            self.connectToHost()
        
        if self.isReady:
            self.readAudio()

    def toDecibel(self, rms):
        return round((20*(math.log(rms) / math.log(10))))

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