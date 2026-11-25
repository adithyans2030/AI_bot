// Minimal voice-activity detector for the shared Google Meet tab's audio.
//
// Meet never plays your own voice back to you, so this channel carries only
// the other participants: anything loud enough for long enough here means
// someone in the class (not the teacher) is speaking. Runs entirely in the
// browser on the audio level alone — nothing is recorded, transcribed or
// sent except the bare fact "someone is speaking".

export function startVoiceActivityDetector(audioContext, stream, { threshold, minSpeechMs, onSpeech, frameMs = 100 }) {
  const source = audioContext.createMediaStreamSource(stream);
  const analyser = audioContext.createAnalyser();
  analyser.fftSize = 1024;
  // Analyser only, never connected to the speakers: no echo, and the tab's
  // own audio keeps playing normally for the teacher.
  source.connect(analyser);

  const samples = new Float32Array(analyser.fftSize);
  let loudMs = 0;

  const timer = setInterval(() => {
    analyser.getFloatTimeDomainData(samples);
    let sum = 0;
    for (let i = 0; i < samples.length; i++) sum += samples[i] * samples[i];
    const rms = Math.sqrt(sum / samples.length);

    if (rms >= threshold) {
      loudMs += frameMs;
      // Short blips (join chimes, a cough) under minSpeechMs are ignored.
      if (loudMs >= minSpeechMs) onSpeech();
    } else {
      loudMs = 0;
    }
  }, frameMs);

  return function stop() {
    clearInterval(timer);
    source.disconnect();
  };
}
