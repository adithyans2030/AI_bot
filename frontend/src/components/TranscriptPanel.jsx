import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { SLIDE_CAPTURE_INTERVAL_SECONDS } from "../config.js";

function speechRecognitionSupported() {
  return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
}

function screenCaptureSupported() {
  return !!(navigator.mediaDevices && navigator.mediaDevices.getDisplayMedia);
}

function fmtTime(epochSeconds) {
  return new Date(epochSeconds * 1000).toLocaleTimeString();
}

export default function TranscriptPanel({ session, entries, onSendChunk }) {
  const [listening, setListening] = useState(false);
  const [micStatus, setMicStatus] = useState(
    speechRecognitionSupported() ? "" : "Web Speech API not supported in this browser — use Chrome, or paste-in mode."
  );
  const [pasteText, setPasteText] = useState("");

  // Slide capture — entirely optional, independent of the mic. See
  // backend/app/slide_vision.py for what happens to these frames: it's a
  // second, supplementary signal for topic matching, never a trigger on
  // its own.
  const [sharingSlide, setSharingSlide] = useState(false);
  const [slideStatus, setSlideStatus] = useState(
    screenCaptureSupported() ? "" : "Screen sharing not supported in this browser."
  );
  const [detectedSlide, setDetectedSlide] = useState(null);

  const recognitionRef = useRef(null);
  const listeningRef = useRef(false);
  const scrollRef = useRef(null);

  const streamRef = useRef(null);
  const videoRef = useRef(null);
  const captureIntervalRef = useRef(null);
  const sharingRef = useRef(false);

  // Stop listening + sharing whenever the session ends.
  useEffect(() => {
    if (!session) {
      if (recognitionRef.current) stopListening();
      if (sharingRef.current) stopSlideCapture();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  // Belt-and-suspenders cleanup if the component itself unmounts mid-share.
  useEffect(() => {
    return () => {
      if (sharingRef.current) stopSlideCapture();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [entries]);

  function ensureRecognition() {
    if (recognitionRef.current) return recognitionRef.current;
    const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognitionImpl();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    recognition.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          onSendChunk(result[0].transcript.trim());
        }
      }
    };

    recognition.onerror = (event) => {
      setMicStatus(`Mic error: ${event.error}`);
    };

    recognition.onend = () => {
      // Browsers stop continuous recognition after periods of silence;
      // restart automatically while the teacher still wants to listen.
      if (listeningRef.current) {
        try {
          recognition.start();
        } catch (_) {
          /* already starting */
        }
      }
    };

    recognitionRef.current = recognition;
    return recognition;
  }

  function stopListening() {
    listeningRef.current = false;
    setListening(false);
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
    setMicStatus("");
  }

  function toggleMic() {
    if (!speechRecognitionSupported()) {
      setMicStatus("Web Speech API not supported in this browser — use Chrome, or paste-in mode.");
      return;
    }
    if (listeningRef.current) {
      stopListening();
      return;
    }
    const recognition = ensureRecognition();
    listeningRef.current = true;
    setListening(true);
    setMicStatus("Listening...");
    try {
      recognition.start();
    } catch (_) {
      /* already started */
    }
  }

  function handleAddPaste() {
    const text = pasteText.trim();
    if (!text) return;
    onSendChunk(text);
    setPasteText("");
  }

  // --- Slide capture ---

  function captureFrame(video) {
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    return canvas.toDataURL("image/jpeg", 0.7); // base64 JPEG, compressed
  }

  async function sendFrame() {
    if (!sharingRef.current || !videoRef.current || !session) return;
    const frame = captureFrame(videoRef.current);
    // Frame is discarded immediately after this call — nothing is kept
    // locally beyond the single in-flight capture.
    try {
      const res = await api.postFrame(session.sessionId, frame);
      if (res.slide && res.slide.confidence === "high") {
        setDetectedSlide(res.slide.slide_title);
      }
    } catch (err) {
      // Non-fatal: a single dropped frame just means this interval's read
      // is skipped, not a reason to interrupt the session or alarm the
      // teacher with an error line.
      console.error("Slide frame send failed:", err);
    }
  }

  function stopSlideCapture() {
    sharingRef.current = false;
    setSharingSlide(false);
    setSlideStatus("");
    setDetectedSlide(null);
    if (captureIntervalRef.current) {
      clearInterval(captureIntervalRef.current);
      captureIntervalRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    videoRef.current = null;
  }

  async function startSlideCapture() {
    if (!screenCaptureSupported()) {
      setSlideStatus("Screen sharing not supported in this browser.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({ video: true });
      const video = document.createElement("video");
      video.srcObject = stream;
      await video.play();

      streamRef.current = stream;
      videoRef.current = video;
      sharingRef.current = true;
      setSharingSlide(true);
      setSlideStatus("Sharing — reading slides every ~" + SLIDE_CAPTURE_INTERVAL_SECONDS + "s");

      // Teacher used the browser's own "Stop sharing" control, not our
      // button — revert cleanly either way.
      stream.getVideoTracks()[0].onended = () => stopSlideCapture();

      captureIntervalRef.current = setInterval(sendFrame, SLIDE_CAPTURE_INTERVAL_SECONDS * 1000);
    } catch (err) {
      // Most commonly: the teacher dismissed the picker. Not an error worth
      // alarming over — sharing is optional and the app works fully without it.
      setSlideStatus(err.name === "NotAllowedError" ? "" : `Could not start sharing: ${err.message}`);
    }
  }

  function toggleSlideCapture() {
    if (sharingRef.current) {
      stopSlideCapture();
    } else {
      startSlideCapture();
    }
  }

  return (
    <section className="panel" id="transcript-panel">
      <h2>Live transcript</h2>
      <div className="row">
        <button onClick={toggleMic} disabled={!session}>
          {listening ? "⏹ Stop listening" : "🎤 Start listening"}
        </button>
        <span className="status-line">{micStatus}</span>
      </div>

      <div className="row">
        <button className="secondary" onClick={toggleSlideCapture} disabled={!session}>
          {sharingSlide ? "⏹ Stop sharing" : "🖥 Share slide (optional)"}
        </button>
        <span className="status-line">
          {slideStatus}
          {detectedSlide ? ` — detected: "${detectedSlide}"` : ""}
        </span>
      </div>

      <span className="eyebrow">Paste-in mode (for testing without a live mic)</span>
      <div className="row">
        <textarea
          rows={2}
          placeholder="Paste a transcript snippet..."
          value={pasteText}
          onChange={(e) => setPasteText(e.target.value)}
        />
        <button className="secondary" onClick={handleAddPaste} disabled={!session}>
          Add
        </button>
      </div>

      <span className="eyebrow">Transcript</span>
      <div className="scroll-box transcript-log" ref={scrollRef}>
        {entries.length === 0 && <div className="empty-hint">Nothing said yet.</div>}
        {entries.map((e, i) => (
          <div className="log-entry" key={i}>
            <span className="ts">{fmtTime(e.timestamp)}</span>
            {e.text}
          </div>
        ))}
      </div>
    </section>
  );
}
