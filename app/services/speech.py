"""Builders for the Web Speech API snippets executed in the browser.

Speech is produced client-side with `speechSynthesis`, so the server never
handles audio - it only hands the browser a small script to run.
"""

import json


def speak_script(sentence: str, voice: str, rate: float) -> str:
    """JavaScript that speaks `sentence` with the chosen voice and rate."""
    return f"""
    (() => {{
      if (!window.speechSynthesis) {{ return; }}
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance({json.dumps(sentence)});
      const wanted = {json.dumps(voice)};
      const v = window.speechSynthesis.getVoices()
                .find(x => window.__voiceLabel(x) === wanted);
      if (v) u.voice = v;
      u.rate = {float(rate)};
      window.speechSynthesis.speak(u);
    }})();
    """


def cancel_script() -> str:
    """JavaScript that stops any utterance currently being spoken."""
    return "window.__stopAll && window.__stopAll();"
