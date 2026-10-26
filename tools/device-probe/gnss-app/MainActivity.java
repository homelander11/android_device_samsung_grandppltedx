/* SPDX-License-Identifier: Apache-2.0 */
package dev.j2prime.gnssprobe;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.location.GnssStatus;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.location.OnNmeaMessageListener;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.util.Locale;

/** Foreground hardware diagnostic. Never reads coordinates, saves files or uses the network. */
public final class MainActivity extends Activity {
    private static final String TAG = "J2PrimeGpsProbe";
    private static final long MAX_DURATION_MS = 10 * 60 * 1000;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private LocationManager manager;
    private TextView status;
    private Button toggle;
    private boolean running, userStopped;
    private long started, elapsed, lastProgress;
    private int seen, used, peakSeen, fixes, mocks, nmea, ttff = -1;
    private float strongest, accuracy = -1;
    private String event = "Ready";

    private final GnssStatus.Callback satellites = new GnssStatus.Callback() {
        @Override public void onStarted() { event = "GPS engine started"; report("ENGINE_STARTED"); }
        @Override public void onStopped() { event = "GPS engine stopped"; report("ENGINE_STOPPED"); }
        @Override public void onFirstFix(int millis) { ttff = millis; report("FIRST_FIX_EVENT"); }
        @Override public void onSatelliteStatusChanged(GnssStatus state) {
            seen = state.getSatelliteCount(); used = 0; strongest = 0;
            peakSeen = Math.max(peakSeen, seen);
            for (int i = 0; i < seen; i++) {
                if (state.usedInFix(i)) used++;
                strongest = Math.max(strongest, state.getCn0DbHz(i));
            }
            report("SATELLITES");
        }
    };
    private final OnNmeaMessageListener sentences = (message, timestamp) -> nmea++;
    private final LocationListener positions = new LocationListener() {
        @Override public void onLocationChanged(Location location) {
            if (location.isFromMockProvider()) { mocks++; report("MOCK_EXCLUDED"); return; }
            if (!LocationManager.GPS_PROVIDER.equals(location.getProvider())) return;
            fixes++;
            accuracy = location.hasAccuracy() ? location.getAccuracy() : -1;
            report("GPS_FIX");
        }
        @Override public void onProviderEnabled(String provider) { report("PROVIDER_ENABLED"); }
        @Override public void onProviderDisabled(String provider) { report("PROVIDER_DISABLED"); }
        @Override public void onStatusChanged(String provider, int value, Bundle extras) { }
    };
    private final Runnable tick = new Runnable() {
        @Override public void run() {
            if (!running) return;
            render();
            if (SystemClock.elapsedRealtime() - lastProgress >= 10000) {
                lastProgress = SystemClock.elapsedRealtime();
                report("PROGRESS");
            }
            if (SystemClock.elapsedRealtime() - started >= MAX_DURATION_MS) {
                stop("Ten-minute test completed"); return;
            }
            handler.postDelayed(this, 1000);
        }
    };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        manager = (LocationManager) getSystemService(LOCATION_SERVICE);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(24, 24, 24, 24);
        status = new TextView(this); status.setTextSize(18);
        layout.addView(status, new LinearLayout.LayoutParams(-1, 0, 1));
        toggle = new Button(this);
        toggle.setOnClickListener(view -> {
            userStopped = running;
            if (running) stop("Stopped"); else start();
        });
        layout.addView(toggle); setContentView(layout); render();
    }

    @Override public void onResume() {
        super.onResume();
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION}, 1);
        } else if (!userStopped) start();
    }

    @Override public void onRequestPermissionsResult(int request, String[] permissions, int[] grants) {
        super.onRequestPermissionsResult(request, permissions, grants);
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)
                == PackageManager.PERMISSION_GRANTED) start();
        else { event = "Location permission required"; render(); }
    }

    private void start() {
        if (running) return;
        seen = used = peakSeen = fixes = mocks = nmea = 0;
        strongest = 0; accuracy = -1; ttff = -1; elapsed = 0;
        started = SystemClock.elapsedRealtime(); lastProgress = started;
        running = true; userStopped = false;
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        event = "Waiting for satellites";
        try {
            boolean sv = manager.registerGnssStatusCallback(satellites, handler);
            boolean nm = manager.addNmeaListener(sentences, handler);
            manager.requestLocationUpdates(LocationManager.GPS_PROVIDER, 1000, 0, positions,
                    Looper.getMainLooper());
            Log.i(TAG, "REQUEST_STARTED STATUS_CALLBACK=" + sv + " NMEA_CALLBACK=" + nm);
            handler.post(tick);
        } catch (RuntimeException failure) {
            stop("Request failed: " + failure.getClass().getSimpleName());
        }
        render();
    }

    private void stop(String reason) {
        if (running) elapsed = SystemClock.elapsedRealtime() - started;
        running = false; handler.removeCallbacks(tick);
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        manager.removeUpdates(positions);
        manager.unregisterGnssStatusCallback(satellites);
        manager.removeNmeaListener(sentences);
        event = reason; report("REQUEST_STOPPED");
    }

    private void report(String kind) {
        Log.i(TAG, kind + " SEEN=" + seen + " USED=" + used + " PEAK_SEEN=" + peakSeen
                + " MAX_CN0=" + strongest + " FIXES=" + fixes + " ACCURACY_M=" + accuracy
                + " TTFF_MS=" + ttff + " NMEA=" + nmea + " MOCKS=" + mocks);
        render();
    }

    private void render() {
        long seconds = (running ? SystemClock.elapsedRealtime() - started : elapsed) / 1000;
        status.setText(String.format(Locale.US,
                "J2 Prime GPS test\n\n%s\nElapsed: %d seconds\n\nSatellites seen: %d (peak %d)"
                + "\nUsed in fix: %d\nStrongest signal: %.1f dB-Hz\n\nGPS fixes: %d"
                + "\nAccuracy: %.1f metres\nFirst fix: %d ms\nNMEA messages: %d"
                + "\n\nKeep this screen open with a clear view of the sky."
                + "\nThe test stops after ten minutes.\nCoordinates are not displayed or saved.",
                event, seconds, seen, peakSeen, used, strongest, fixes, accuracy, ttff, nmea));
        toggle.setText(running ? "Stop GPS test" : "Start GPS test");
    }

    @Override public void onPause() { stop("Paused"); super.onPause(); }
}
