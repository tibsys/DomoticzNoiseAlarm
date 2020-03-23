import socket
import sys
from pymedia import muxer

url = "http://192.168.1.51:8080/audio.wav"

dm = muxer.Demuxer( "audio" )

inSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
inSock.connect(("192.168.1.51", 8080))
inSock.send("GET " + "/audio.wav" + " HTTP/1.0\r\nHost: " +"192.168.1.51" "\r\n\r\n")

s = inSock.recv( 512 )
snd = None
resampler = None
dec = None

while len( s ):
    print("data read")

    frames = dm.parse( s )
    if frames:
      for fr in frames:
        # Assume for now only audio streams
 
        if dec is None:
          print(dm.getInfo())
          print(dm.streams)
          dec = acodec.Decoder( dm.streams[ fr[ 0 ] ] )
         
        r = dec.decode( fr[ 1 ] )
 
        if r and r.data:
          if snd is None:
            print('Opening sound with %d channels -> %s' % ( r.channels, snds[ card ][ 'name' ] ))
            snd = sound.Output( int( r.sample_rate* rate ), r.channels, sound.AFMT_S16_LE, card )
            if rate < 1 or rate > 1:
              resampler = sound.Resampler( (r.sample_rate,r.channels), (int(r.sample_rate/rate),r.channels) )
              print('Sound resampling %d->%d' % ( r.sample_rate, r.sample_rate/rate ))
           
          data = r.data
          if resampler:
            data = resampler.resample( data )
 
          ## Do the job here
    if tt> 0:
      if snd and snd.getPosition() > tt:
        break

    s = inSock.recv( 512 )

inSock.close()
