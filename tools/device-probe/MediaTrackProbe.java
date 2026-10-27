/* SPDX-License-Identifier: Apache-2.0 */
/* Read-only saved-clip diagnostics. Run with app_process, not bare dalvikvm.
 * Reports packet/timestamp counts, aggregate PCM levels and optional decoded
 * frame diversity. Does not save decoded media or print pixels/audio samples.
 * These checks do not establish normal surface playback or image correctness.
 */
import android.media.MediaExtractor;
import android.media.MediaFormat;
import android.media.MediaCodec;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.HashSet;
import java.util.zip.CRC32;
public class MediaTrackProbe {
 static void meta(String path,int track) throws Exception {
  MediaExtractor e=new MediaExtractor();e.setDataSource(path);e.selectTrack(track);
  MediaFormat f=e.getTrackFormat(track);String mime=f.getString(MediaFormat.KEY_MIME);
  long first=-1,last=-1,min=Long.MAX_VALUE,max=0;int count=0,back=0;HashSet<Long> hashes=new HashSet<Long>();
  ByteBuffer b=ByteBuffer.allocate(2*1024*1024);CRC32 crc=new CRC32();
  while(count<2000){b.clear();int size=e.readSampleData(b,0);if(size<0)break;long t=e.getSampleTime();if(first<0)first=t;if(last>=0){long d=t-last;if(d<0)back++;else{min=Math.min(min,d);max=Math.max(max,d);}}last=t;crc.reset();crc.update(b.array(),0,size);hashes.add(crc.getValue());count++;e.advance();}
  System.out.println("TRACK="+track+" MIME="+mime+" FORMAT="+f+" PACKETS="+count+" UNIQUE_PACKETS="+hashes.size()+" FIRST_US="+first+" LAST_US="+last+" MIN_STEP_US="+min+" MAX_STEP_US="+max+" BACKWARDS="+back);e.release();
 }
 static void audio(String path,int track) throws Exception {
  MediaExtractor e=new MediaExtractor();e.setDataSource(path);e.selectTrack(track);MediaFormat f=e.getTrackFormat(track);
  MediaCodec c=MediaCodec.createDecoderByType(f.getString(MediaFormat.KEY_MIME));boolean started=false;
  long samples=0,pairs=0;double squares=0,left2=0,right2=0,mono2=0,cross=0;int left=0;int peak=0,chunks=0;boolean inputDone=false,outputDone=false;long until=android.os.SystemClock.elapsedRealtime()+10000;
  try{c.configure(f,null,null,0);c.start();started=true;MediaCodec.BufferInfo info=new MediaCodec.BufferInfo();
   while(!outputDone && chunks<700 && android.os.SystemClock.elapsedRealtime()<until){
    if(!inputDone){int i=c.dequeueInputBuffer(1000);if(i>=0){ByteBuffer b=c.getInputBuffer(i);int n=e.readSampleData(b,0);if(n<0){c.queueInputBuffer(i,0,0,0,MediaCodec.BUFFER_FLAG_END_OF_STREAM);inputDone=true;}else{c.queueInputBuffer(i,0,n,e.getSampleTime(),0);e.advance();}}}
    int o=c.dequeueOutputBuffer(info,1000);if(o>=0){
     ByteBuffer b=c.getOutputBuffer(o);if(b!=null && info.size>0){b.order(ByteOrder.LITTLE_ENDIAN);b.position(info.offset);b.limit(info.offset+info.size);while(b.remaining()>=2){int v=b.getShort();samples++;squares+=(double)v*v;peak=Math.max(peak,Math.abs(v));if(f.getInteger(MediaFormat.KEY_CHANNEL_COUNT)==2){if((samples&1)==1)left=v;else{pairs++;left2+=(double)left*left;right2+=(double)v*v;mono2+=(double)(left+v)*(left+v)/4;cross+=(double)left*v;}}}chunks++;}
     outputDone=(info.flags&MediaCodec.BUFFER_FLAG_END_OF_STREAM)!=0;c.releaseOutputBuffer(o,false);
    }
   }
   System.out.println("AUDIO_DECODE chunks="+chunks+" samples="+samples+" rms="+(samples==0?-1:Math.sqrt(squares/samples))+" peak="+peak+" EOS="+outputDone+" L_RMS="+(pairs==0?-1:Math.sqrt(left2/pairs))+" R_RMS="+(pairs==0?-1:Math.sqrt(right2/pairs))+" MONO_RMS="+(pairs==0?-1:Math.sqrt(mono2/pairs))+" LR_CORRELATION="+(left2*right2==0?0:cross/Math.sqrt(left2*right2))+" FORMAT="+c.getOutputFormat());
  }finally{if(started)c.stop();c.release();e.release();}
 }
 static void video(String path,int track,String codecName) throws Exception {
  MediaExtractor e=new MediaExtractor();e.setDataSource(path);e.selectTrack(track);MediaFormat f=e.getTrackFormat(track);MediaCodec c=MediaCodec.createByCodecName(codecName);boolean started=false;
  int frames=0;HashSet<Long> unique=new HashSet<Long>();CRC32 crc=new CRC32();byte[] block=new byte[8192];boolean inDone=false,outDone=false;long until=android.os.SystemClock.elapsedRealtime()+10000;
  try{c.configure(f,null,null,0);c.start();started=true;MediaCodec.BufferInfo info=new MediaCodec.BufferInfo();
   while(!outDone && frames<16 && android.os.SystemClock.elapsedRealtime()<until){
    if(!inDone){int i=c.dequeueInputBuffer(1000);if(i>=0){ByteBuffer b=c.getInputBuffer(i);int n=e.readSampleData(b,0);if(n<0){c.queueInputBuffer(i,0,0,0,MediaCodec.BUFFER_FLAG_END_OF_STREAM);inDone=true;}else{c.queueInputBuffer(i,0,n,e.getSampleTime(),0);e.advance();}}}
    int o=c.dequeueOutputBuffer(info,1000);if(o>=0){ByteBuffer b=c.getOutputBuffer(o);if(b!=null && info.size>0){b.position(info.offset);b.limit(info.offset+info.size);crc.reset();while(b.hasRemaining()){int n=Math.min(block.length,b.remaining());b.get(block,0,n);crc.update(block,0,n);}unique.add(crc.getValue());frames++;}outDone=(info.flags&MediaCodec.BUFFER_FLAG_END_OF_STREAM)!=0;c.releaseOutputBuffer(o,false);}
   }
   System.out.println("VIDEO_DECODE codec="+codecName+" frames="+frames+" uniqueFrames="+unique.size()+" EOS="+outDone+" FORMAT="+c.getOutputFormat());
  }finally{if(started)c.stop();c.release();e.release();}
 }
 public static void main(String[] args)throws Exception {MediaExtractor e=new MediaExtractor();e.setDataSource(args[0]);int tracks=e.getTrackCount();int audio=-1,video=-1;for(int i=0;i<tracks;i++){String mime=e.getTrackFormat(i).getString(MediaFormat.KEY_MIME);if(mime.startsWith("audio/"))audio=i;if(mime.startsWith("video/"))video=i;}e.release();for(int i=0;i<tracks;i++)meta(args[0],i);if(args.length>1 && video>=0)video(args[0],video,args[1]);else if(audio>=0)audio(args[0],audio);}
}
