/* SPDX-License-Identifier: Apache-2.0 */
/* Bounded, read-only video colour diagnostics. Run through app_process.
 * Prints aggregate plane levels and strides only; never saves decoded media.
 */
import android.graphics.Rect;
import android.media.Image;
import android.media.MediaCodec;
import android.media.MediaExtractor;
import android.media.MediaFormat;
import java.nio.ByteBuffer;
import java.util.Locale;

public class VideoColourProbe {
    static double mean(Image.Plane plane, Rect crop, int sub, boolean centre) {
        int left = crop.left / sub, top = crop.top / sub;
        int width = crop.width() / sub, height = crop.height() / sub;
        if (centre) {
            left += width / 3;
            top += height / 3;
            width /= 3;
            height /= 3;
        }
        ByteBuffer data = plane.getBuffer();
        int base = data.position(), row = plane.getRowStride(), pixel = plane.getPixelStride();
        long sum = 0, samples = 0;
        for (int y = top; y < top + height; y += 4) {
            for (int x = left; x < left + width; x += 4) {
                int offset = base + y * row + x * pixel;
                if (offset < base || offset >= data.limit()) {
                    throw new IllegalArgumentException("plane layout exceeds its buffer");
                }
                sum += data.get(offset) & 255;
                samples++;
            }
        }
        if (samples == 0) throw new IllegalArgumentException("empty crop");
        return (double) sum / samples;
    }

    public static void main(String[] args) {
        try {
            run(args);
        } catch (Exception error) {
            System.err.println("COLOUR_PROBE_FAILED " + error.getClass().getSimpleName() + ": " + error.getMessage());
            System.exit(1);
        }
    }

    static void run(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("Supply a local video path");
        if (!new java.io.File(args[0]).isFile()) throw new IllegalArgumentException("Input video is absent or unreadable");
        MediaExtractor extractor = new MediaExtractor();
        MediaCodec decoder = null;
        boolean started = false;
        try {
            extractor.setDataSource(args[0]);
            MediaFormat format = null;
            for (int i = 0; i < extractor.getTrackCount(); i++) {
                MediaFormat candidate = extractor.getTrackFormat(i);
                if (candidate.getString(MediaFormat.KEY_MIME).startsWith("video/")) {
                    extractor.selectTrack(i);
                    format = candidate;
                    break;
                }
            }
            if (format == null) throw new IllegalArgumentException("No video track");
            System.out.println("VIDEO_FORMAT=" + format);
            decoder = MediaCodec.createByCodecName("OMX.google.h264.decoder");
            decoder.configure(format, null, null, 0);
            decoder.start();
            started = true;
            boolean inputDone = false;
            int frames = 0;
            long deadline = android.os.SystemClock.elapsedRealtime() + 10000;
            MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
            while (frames < 8 && android.os.SystemClock.elapsedRealtime() < deadline) {
                if (!inputDone) {
                    int input = decoder.dequeueInputBuffer(1000);
                    if (input >= 0) {
                        ByteBuffer buffer = decoder.getInputBuffer(input);
                        int size = extractor.readSampleData(buffer, 0);
                        if (size < 0) {
                            decoder.queueInputBuffer(input, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM);
                            inputDone = true;
                        } else {
                            decoder.queueInputBuffer(input, 0, size, extractor.getSampleTime(), 0);
                            extractor.advance();
                        }
                    }
                }
                int output = decoder.dequeueOutputBuffer(info, 1000);
                if (output < 0) continue;
                try {
                    if (info.size > 0) {
                        Image image = decoder.getOutputImage(output);
                        if (image == null) throw new IllegalStateException("Decoder does not expose YUV planes");
                        try {
                            Image.Plane[] planes = image.getPlanes();
                            if (planes.length != 3) throw new IllegalStateException("Expected three YUV planes");
                            Rect crop = image.getCropRect();
                            for (boolean centre : new boolean[] {false, true}) {
                                double y = mean(planes[0], crop, 1, centre);
                                double u = mean(planes[1], crop, 2, centre);
                                double v = mean(planes[2], crop, 2, centre);
                                System.out.printf(Locale.US,
                                    "FRAME=%d PTS_US=%d REGION=%s Y=%.2f U=%.2f V=%.2f STRIDES=%d/%d/%d PIXEL=%d/%d/%d%n",
                                    frames, info.presentationTimeUs, centre ? "centre" : "whole", y, u, v,
                                    planes[0].getRowStride(), planes[1].getRowStride(), planes[2].getRowStride(),
                                    planes[0].getPixelStride(), planes[1].getPixelStride(), planes[2].getPixelStride());
                            }
                            frames++;
                        } finally {
                            image.close();
                        }
                    }
                } finally {
                    decoder.releaseOutputBuffer(output, false);
                }
                if ((info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0) break;
            }
            if (frames == 0) throw new IllegalStateException("No decoded frames within limit");
            System.out.println("DECODED_COLOUR_FRAMES=" + frames);
        } finally {
            if (decoder != null) {
                try { if (started) decoder.stop(); } finally { decoder.release(); }
            }
            extractor.release();
        }
    }
}
