/* SPDX-License-Identifier: Apache-2.0 */
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.AudioRecordingConfiguration;
import android.os.SystemClock;
import android.system.Os;

/** Three-second AudioRecord diagnostic. Keeps aggregate levels, never an audio file. */
public final class MicLevelProbe {
    public static void main(String[] args) throws Exception {
        if (Os.getuid() != 0 || args.length != 1) {
            throw new IllegalArgumentException("Authorized root only: SOURCE (1, 6, 7 or 9)");
        }
        int source = Integer.parseInt(args[0]);
        if (source != 1 && source != 6 && source != 7 && source != 9) {
            throw new IllegalArgumentException("Use MIC=1, VOICE_RECOGNITION=6, VOICE_COMMUNICATION=7 or UNPROCESSED=9");
        }
        final int rate = 16000;
        int minimum = AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT);
        if (minimum <= 0) throw new IllegalStateException("Invalid min buffer " + minimum);
        AudioRecord input = new AudioRecord(source, rate, AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT, Math.max(minimum * 2, 4096));
        try {
            if (input.getState() != AudioRecord.STATE_INITIALIZED) {
                throw new IllegalStateException("AudioRecord initialization failed");
            }
            input.startRecording();
            if (input.getRecordingState() != AudioRecord.RECORDSTATE_RECORDING) {
                throw new IllegalStateException("AudioRecord did not start");
            }
            short[] buffer = new short[1024];
            int samples = 0, nonzero = 0, peak = 0, minimumSample = 32767;
            int maximumSample = -32768, transitions = 0, previous = 0;
            double squares = 0;
            long start = SystemClock.elapsedRealtime();
            while (samples < rate * 3 && SystemClock.elapsedRealtime() - start < 6000) {
                int count = input.read(buffer, 0, Math.min(buffer.length, rate * 3 - samples));
                if (count <= 0) throw new IllegalStateException("AudioRecord read " + count);
                for (int i = 0; i < count; i++) {
                    int value = buffer[i];
                    if (value != 0) nonzero++;
                    minimumSample = Math.min(minimumSample, value);
                    maximumSample = Math.max(maximumSample, value);
                    if (samples + i > 0 && value != previous) transitions++;
                    previous = value;
                    peak = Math.max(peak, Math.abs(value));
                    squares += (double) value * value;
                }
                samples += count;
            }
            AudioRecordingConfiguration config = input.getActiveRecordingConfiguration();
            String silenced = config == null ? "unknown" : Boolean.toString(config.isClientSilenced());
            System.out.println("SOURCE=" + source + " RATE=" + rate + " SAMPLES=" + samples
                    + " NONZERO=" + nonzero + " PEAK=" + peak
                    + " RMS=" + Math.sqrt(squares / Math.max(samples, 1))
                    + " MIN=" + minimumSample + " MAX=" + maximumSample
                    + " TRANSITIONS=" + transitions + " SILENCED=" + silenced);
            if (config == null || config.isClientSilenced()) {
                System.out.println("INCONCLUSIVE: background capture can be silenced by Android; "
                        + "test a foreground recorder before diagnosing the HAL.");
            }
        } finally {
            if (input.getRecordingState() == AudioRecord.RECORDSTATE_RECORDING) input.stop();
            input.release();
        }
    }
}
