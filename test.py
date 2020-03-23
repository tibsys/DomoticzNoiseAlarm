import sys
import wave
import socket
import io
import audioop
import math

#channels = 1
#sample_rate = 44100
#sample_width = 2  # 16 bit pcm
inSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    res = inSock.connect(("192.168.1.51", 8080))
except ConnectionRefusedError:
    print("Erreur de connexion")
    quit()

connString = "GET " +"/audio.wav" +" HTTP/1.0\r\nHost: " +"192.168.1.51" +"\r\n\r\n"
b = bytearray()
b.extend(map(ord, connString))
try:
    inSock.send(b)
except BrokenPipeError:
    print("Connexion perdue")
    quit()

while True:    
    s = inSock.recv( 300000 )
    print("data read from webcam, size: ", len(s), " bytes")

    #s_ = s.decode()
    if s.startswith(b"HTTP/1.1 200 OK"):
        print("En-tête HTTP reçu")

    if len(s) > 0:
        #print(s)
                    
        rms = audioop.rms(s, 2)
        print("rms: ", rms)
        
        dB = 20*(math.log(rms) / math.log(10))
        print("decibels", dB)
    
inSock.close()