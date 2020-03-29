import numpy as np
import scipy.signal as sg
import sys
import math
import audioop
import socket
import io
import base64
import wave
import re 
import struct
import audioop
from scipy.signal import butter, lfilter

inSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    inSock.connect(("192.168.1.51", 80))
    print("Connection to the webcam OK")
except:
    print("Connection to the webcam refused")
    quit()

print("Querying audio stream")

username = "admin"
password = "EWrkdSwa"

#TODO: check if Mode1 starts with '/'
connString = "GET /audio.cgi HTTP/1.0\r\nHost: 192.168.1.51\r\n"

data = bytearray(username +":" +password, "utf-8")
token = base64.encodebytes(data)
connString += ("Authorization: Basic " +token.decode("utf-8") +"\r\n")

# Terminate GET request string
connString += "\r\n"

try:
    b = bytearray()
    b.extend(map(ord, connString))
    inSock.send(b)            
except BrokenPipeError:
    print("Connection to the webcam interrupted")
    quit()

#print(connString)
audio = open("/Users/tristan/Downloads/audio.wav", "w+b")
audio_low = open("/Users/tristan/Downloads/audio_low.wav", "w+b")

#audio_low.setnchannels(1)
#audio_low.setsampwidth(2)
#audio_low.setframerate(8000)

headersReceived = False
fr = 8000
wav_header = None
cnt = 0
output_signal = bytearray() 
N = 4
nyq = 0.5 * fr
lowcut = 100 / nyq
recvSignal = bytearray()

#filter_ = Butter(btype="low", cutoff=300, rolloff=48, sampling=8000)

def unpack_wave(data):
    dlen=(len(data)/2)
    return struct.unpack('%ih' % dlen, data)

def wave_shorts_to_floats(ints):
    return [i * 1.0/32768 for i in ints]

def floats_to_wave_ints(floats):
    return [int(round(f * 32767)) for f in floats]

def pack_wave(data):
    dlen=len(data)
    return struct.pack('<%dh' % dlen, *data)

def toDecibel(rms):
    return round((20*(math.log(rms) / math.log(10))))

while True:
    print("Wait for data")
    s = inSock.recv( 4096 )

    if not headersReceived:
        print("Receiving HTTP headers")
        print("Received " +str(len(s)) +" bytes of data")       

        if s.startswith(b"RIFF"):
            headersReceived = True               
            wav_header = s[0:44]
            audio.write(wav_header)  
            audio_low.write(wav_header)  
            s = s[44:]            

    if headersReceived:
        if len(s) == 0:
            continue

        recvSignal = s
        #if len(recvSignal) < 8192:
        #    continue
        print("Received " +str(len(recvSignal)) +" bytes of raw audio")            
        audio.write(recvSignal)

        # Apply filter
        #x = np.frombuffer(s, np.int16) / 2.**15
        #b, a = sg.butter(4, lowcut, 'low')
        #x_fil = sg.lfilter(b, a, s)
        #x_fil = sg.filtfilt(b, a, x)
        #Bparam, Aparam = sg.iirfilter(2, lowcut, btype = 'lowpass', analog = False, ftype = 'butter')
        #Z, P, K = sg.tf2zpk(Bparam, Aparam)
        #sos = sg.zpk2sos(Z, P, K)

        #Bparam, Aparam = sg.iirfilter(2, lowcut, btype = 'lowpass', analog = False, ftype = 'butter')       # 2nd order Butterworth coefficients
        #Z = sg.lfilter_zi(Bparam, Aparam) # Part of the init conditions calc
        #IC = Z * (prevSignal[::-1])[0:2]      # Reverse prevSignal and then grab  only the last two elements
        #filteredSignal, _ = sg.lfilter(Bparam, Aparam, s, zi = IC) # Result is continuous and clear
        #prevSignal = filteredSignal           # Save for the next pass

        # Unpack wave
        wav = unpack_wave(recvSignal)

        # Convert to floats        
        floats = wave_shorts_to_floats(wav)
        
        # Apply filter
        b, a = sg.butter(4, lowcut, 'low')
        filteredSignal = lfilter(b, a, floats) 

        # Convert to ints
        ints = floats_to_wave_ints(filteredSignal)
        #print(ints)

        # Pack wave
        outSignal = pack_wave(ints)

        # Write to file
        audio_low.write(outSignal)

        # Calculate decibelqs
        rmsSource = audioop.rms(recvSignal, 2)
        rmsOut = audioop.rms(outSignal, 2)
        print("rmsSource=" +str(rmsSource))
        print("dbSource=" +str(toDecibel(rmsSource)))
        print("rmsOut=" +str(rmsOut))
        print("dbOut=" +str(toDecibel(rmsOut)))

        cnt = cnt+1
        #s[:] = 0

audio.close()   
audio_low.close()
