import numpy as np
import wave
import io
import re

# ----------------------------------------------------------------------
#  Short-word list (muscle-memory ≤ 3 letters)
# ----------------------------------------------------------------------
SHORT_WORDS = {
    "a", "an", "the", "and", "or", "but", "nor", "so", "yet",
    "i", "me", "my", "you", "your", "he", "she", "it", "we", "they",
    "is", "am", "are", "was", "were", "be", "been", "being",
    "of", "in", "on", "at", "to", "for", "with", "by", "from", "up", "out",
    "do", "does", "did", "has", "have", "had", "can", "will", "would", "as",
    "if", "no", "not", "yes", "oh", "um"
}


# ----------------------------------------------------------------------
#  Helper: hyphen → dash expansion
# ----------------------------------------------------------------------
def expand_hyphens(text: str) -> list[str]:
    words = []
    for token in re.findall(r"[\w'-]+|[^\w\s]", text):
        token = token.strip()
        if not token:
            continue
        if '-' in token and token.replace('-', '').isalpha():
            parts = token.split('-')
            if len(parts) > 1:
                words.extend(parts)
                words.insert(-len(parts) + 1, "dash")
            else:
                words.append(token)
        else:
            words.append(token)
    return words

# ----------------------------------------------------------------------
#  Helper: smart 2-word (or 3-word) chunks
# ----------------------------------------------------------------------
def make_chunks(words: list[str]) -> list[list[str]]:
    chunks = []
    i = 0
    while i < len(words):
        window = words[i:i+3]

        # never start a chunk with a short word (except the very first chunk)
        if chunks and window and window[0].lower() in SHORT_WORDS:
            chunks[-1].append(window[0])
            i += 1
            continue

        # prefer 2-word chunks
        if len(window) >= 2:
            chunk = window[:2]
            # pull in a third short word if it exists
            if len(window) == 3 and window[2].lower() in SHORT_WORDS:
                chunk = window[:3]
        else:
            chunk = window

        chunks.append(chunk)
        i += len(chunk)
    return chunks

# ----------------------------------------------------------------------
#  Helper: silence with 5 ms fade-in/out
# ----------------------------------------------------------------------
def insert_silence(master: wave.Wave_write, seconds: float):
    rate = master.getframerate()
    total = int(rate * seconds)
    if total <= 0:
        return

    fade = int(rate * 0.005)                     # 5 ms
    fade = min(fade, total // 2)

    silence = np.zeros(total, dtype=np.int16)

    # fade-in
    if fade:
        fade_in = np.linspace(0, 1, fade, endpoint=False)
        silence[:fade] = (silence[:fade].astype(np.float32) * fade_in).astype(np.int16)

    # fade-out
    if fade and total > fade:
        fade_out = np.linspace(1, 0, fade, endpoint=False)
        silence[-fade:] = (silence[-fade:].astype(np.float32) * fade_out).astype(np.int16)

    master.writeframes(silence.tobytes())

# ----------------------------------------------------------------------
#  Helper: fade-in the *beginning* of a chunk (5 ms)
# ----------------------------------------------------------------------
def fadein_start(chunk_io: io.BytesIO, master: wave.Wave_write):
    rate = master.getframerate()
    fade = int(rate * 0.008)          # 5 ms
    if fade == 0:
        master.writeframes(chunk_io.getvalue())
        return

    chunk_io.seek(0)
    data = np.frombuffer(chunk_io.read(), dtype=np.int16)

    if len(data) <= fade:
        master.writeframes(data.tobytes())
        return

    head = data[:fade]
    fade_in = np.linspace(0, 1, fade, endpoint=False)
    head = (head.astype(np.float32) * fade_in).astype(np.int16)

    master.writeframes(head.tobytes())
    master.writeframes(data[fade:].tobytes())

# ----------------------------------------------------------------------
#  Helper: cross-fade the *end* of a chunk (5 ms) → no pop
# ----------------------------------------------------------------------
def crossfade_end(chunk_io: io.BytesIO, master: wave.Wave_write):
    """Read the last 5 ms of the chunk, fade it to zero, then write it."""
    rate = master.getframerate()
    fade = int(rate * 0.005)
    if fade == 0:
        master.writeframes(chunk_io.getvalue())
        return

    # read the whole chunk as int16
    chunk_io.seek(0)
    data = np.frombuffer(chunk_io.read(), dtype=np.int16)

    if len(data) <= fade:
        # chunk shorter than fade → just write it
        master.writeframes(data.tobytes())
        return

    # fade the tail
    tail = data[-fade:]
    fade_out = np.linspace(1, 0, fade, endpoint=False)
    tail = (tail.astype(np.float32) * fade_out).astype(np.int16)

    # write everything up to the tail, then the faded tail
    master.writeframes(data[:-fade].tobytes())
    master.writeframes(tail.tobytes())
