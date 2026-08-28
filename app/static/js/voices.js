// Helpers used by the server-sent speech snippets.

// A stable label so Python and JS agree on which voice was picked.
window.__voiceLabel = (v) => v.name + ' (' + v.lang + ')';

window.__voiceList = () => {
  const vs = window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
  return vs.map(window.__voiceLabel);
};

if (window.speechSynthesis) {
  window.speechSynthesis.onvoiceschanged = () =>
    window.dispatchEvent(new Event('voicesready'));
}
