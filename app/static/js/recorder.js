// Microphone capture, upload, and playback of cloned speech.
// getUserMedia needs a secure context - localhost counts, so this works over
// plain http on the machine running Docker.

window.__rec = { chunks: [], recorder: null, blob: null, startedAt: 0 };

window.__recSupported = () =>
  !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);

window.__recStart = async () => {
  if (!window.__recSupported()) {
    return { ok: false, error: 'This browser cannot record audio.' };
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = new MediaRecorder(stream);
    window.__rec.chunks = [];
    window.__rec.blob = null;
    recorder.ondataavailable = (e) => { if (e.data && e.data.size) window.__rec.chunks.push(e.data); };
    recorder.onstop = () => {
      window.__rec.blob = new Blob(window.__rec.chunks, { type: recorder.mimeType || 'audio/webm' });
      stream.getTracks().forEach((t) => t.stop());
    };
    recorder.start();
    window.__rec.recorder = recorder;
    window.__rec.startedAt = Date.now();
    return { ok: true };
  } catch (e) {
    // Most often the user dismissed the microphone permission prompt.
    return { ok: false, error: String((e && e.message) || e) };
  }
};

window.__recStop = () => new Promise((resolve) => {
  const recorder = window.__rec.recorder;
  if (!recorder || recorder.state === 'inactive') {
    return resolve({ ok: false, error: 'Not currently recording.' });
  }
  const seconds = (Date.now() - window.__rec.startedAt) / 1000;
  recorder.addEventListener('stop', () => resolve({ ok: true, seconds }), { once: true });
  recorder.stop();
  window.__rec.recorder = null;
});

window.__recUpload = async (name) => {
  const blob = window.__rec.blob;
  if (!blob) return { ok: false, error: 'Nothing has been recorded yet.' };
  const type = blob.type || '';
  const ext = type.includes('ogg') ? 'ogg' : type.includes('mp4') ? 'mp4' : 'webm';
  const form = new FormData();
  form.append('file', blob, 'recording.' + ext);
  form.append('name', name || 'My voice');
  try {
    const res = await fetch('/api/voices', { method: 'POST', body: form });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, error: data.detail || ('Upload failed (' + res.status + ')') };
    window.__rec.blob = null;
    return { ok: true, voice: data };
  } catch (e) {
    return { ok: false, error: String((e && e.message) || e) };
  }
};

// Ask the server to render text in a stored voice, then play what comes back.
window.__speakCloned = async (voiceId, text, rate) => {
  try {
    const res = await fetch('/api/speak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ voice_id: voiceId, text: text }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      return { ok: false, error: data.detail || ('Synthesis failed (' + res.status + ')') };
    }
    const url = URL.createObjectURL(await res.blob());
    window.__stopAll();
    const audio = new Audio(url);
    audio.playbackRate = rate || 1;
    audio.onended = () => URL.revokeObjectURL(url);
    window.__clonedAudio = audio;
    await audio.play();
    return { ok: true };
  } catch (e) {
    return { ok: false, error: String((e && e.message) || e) };
  }
};

// Play an audio URL (the Voices table's preview button). The promise settles
// when playback ends or is stopped, which is what flips the button back.
window.__playUrl = (url) => new Promise((resolve) => {
  window.__stopAll();
  const audio = new Audio(url);
  window.__clonedAudio = audio;
  let settled = false;
  const finish = (result) => { if (!settled) { settled = true; resolve(result); } };
  audio.onended = () => finish({ ok: true });
  audio.onpause = () => finish({ ok: true });   // covers __stopAll()
  audio.onerror = () => finish({ ok: false, error: 'Could not play that recording.' });
  audio.play().catch((e) => finish({ ok: false, error: String((e && e.message) || e) }));
});

// One stop button for both engines.
window.__stopAll = () => {
  if (window.speechSynthesis) window.speechSynthesis.cancel();
  const audio = window.__clonedAudio;
  if (audio) { audio.pause(); audio.currentTime = 0; }
};
