import { useEffect, useRef, useState } from "react";

function speechRecognitionSupported() {
  return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
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

  const recognitionRef = useRef(null);
  const listeningRef = useRef(false);
  const scrollRef = useRef(null);

  // Stop listening whenever the session ends.
  useEffect(() => {
    if (!session && recognitionRef.current) {
      stopListening();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

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

  return (
    <section className="panel" id="transcript-panel">
      <h2>3. Live transcript</h2>
      <div className="row">
        <button onClick={toggleMic} disabled={!session}>
          {listening ? "⏹ Stop listening" : "🎤 Start listening"}
        </button>
        <span className="status-line">{micStatus}</span>
      </div>

      <label>Paste-in mode (for testing without a live mic)</label>
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

      <label>Transcript</label>
      <div className="scroll-box" ref={scrollRef}>
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
