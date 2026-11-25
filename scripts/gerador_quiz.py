"""Gerador de Shorts de quiz — Curioso em 60s.

Uso: python3 gerador_quiz.py roteiro.json saida.mp4
roteiro.json = {"gancho": "...", "fala_gancho": "...", "perguntas": [
   {"pergunta": "...", "opcoes": ["A","B","C"], "correta": 1, "fato": "..."}, ...],
 "fala_final": "..."}
"""
import json, math, os, shutil, subprocess, sys, wave, textwrap
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
VOICE = os.path.join(HERE, "voz", "pt_BR-faber-medium.onnx")
POP = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
W, H, FPS, SR = 1080, 1920, 30, 22050
BG1, BG2 = (14, 10, 40), (60, 20, 110)
YEL, WHITE, GREEN, BOX = (255, 204, 0), (255, 255, 255), (60, 220, 120), (40, 25, 80)
HANDLE = "@curiosoem60s.br"
TMP = os.path.join(HERE, "_tmp")

# ---------------- áudio ----------------
def tts(text, name):
    path = os.path.join(TMP, name + ".wav")
    subprocess.run([sys.executable, "-m", "piper", "-m", VOICE, "-f", path,
                    "--length-scale", "0.92"], input=text.encode(), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with wave.open(path) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    return a

def tone(freq, dur, vol=0.3, decay=8):
    t = np.arange(int(SR * dur)) / SR
    return vol * np.sin(2 * np.pi * freq * t) * np.exp(-decay * t)

def tick():
    return tone(1800, 0.06, 0.25, 40)

def ding():
    return tone(1318, 0.6, 0.35, 5) + tone(1760, 0.6, 0.2, 6)

def music(dur):
    """Loop simples e animado (arpejo) gerado na hora — sem direitos autorais."""
    bpm, n = 112, int(SR * dur)
    out = np.zeros(n, np.float32)
    step = 60 / bpm / 2
    chords = [[261.6, 329.6, 392.0], [220.0, 261.6, 329.6], [174.6, 220.0, 261.6], [196.0, 246.9, 293.7]]
    i = 0
    while i * step < dur:
        ch = chords[(i // 8) % 4]
        f = ch[i % 3] * (2 if i % 4 == 3 else 1)
        s = tone(f, step * 1.5, 0.05, 6)
        a = int(i * step * SR)
        out[a:a + len(s)] += s[: max(0, n - a)]
        if i % 2 == 0:  # bumbo leve
            k = tone(70, 0.15, 0.08, 25)
            out[a:a + len(k)] += k[: max(0, n - a)]
        i += 1
    return out

# ---------------- visual ----------------
_base = None
def base():
    global _base
    if _base is None:
        g = np.linspace(0, 1, H)[:, None]
        g = np.sin(np.pi * g)
        arr = np.zeros((H, W, 3), np.float32)
        for c in range(3):
            arr[:, :, c] = BG1[c] + (BG2[c] - BG1[c]) * g
        _base = Image.fromarray(arr.astype(np.uint8))
    return _base.copy()

F = {}
def font(s):
    if s not in F:
        F[s] = ImageFont.truetype(POP, s)
    return F[s]

def ctext(d, txt, size, y, fill):
    f = font(size)
    b = d.textbbox((0, 0), txt, font=f)
    d.text(((W - (b[2] - b[0])) / 2 - b[0], y), txt, font=f, fill=fill)

def wrap(txt, width):
    return textwrap.wrap(txt, width)

def frame(state, t_global, total):
    im = base(); d = ImageDraw.Draw(im)
    # barra de progresso (ajuda retenção)
    d.rectangle([0, 0, int(W * t_global / total), 14], fill=YEL)
    kind = state["kind"]
    if kind == "gancho":
        ctext(d, "?", 260, 380, YEL)
        y = 760
        for line in wrap(state["texto"], 14):
            ctext(d, line, 120, y, WHITE); y += 150
    elif kind == "final":
        ctext(d, "Quantas você", 104, 600, WHITE)
        ctext(d, "acertou?", 130, 730, YEL)
        ctext(d, "0, 1, 2 ou 3?", 80, 960, WHITE)
        ctext(d, "Comenta aí! 👇".replace(" 👇", ""), 80, 1070, YEL)
        ctext(d, "Segue pra mais 1 por dia", 54, 1260, (200, 185, 235))
    else:
        q = state["q"]
        ctext(d, f"PERGUNTA {state['n']}/{state['tot']}", 60, 170, YEL)
        y = 300
        for line in wrap(q["pergunta"], 18):
            ctext(d, line, 86, y, WHITE); y += 108
        y0 = max(y + 70, 760)
        for k, o in enumerate(q["opcoes"]):
            yy = y0 + k * 175
            ok = kind == "resp" and k == q["correta"]
            dim = kind == "resp" and not ok
            d.rounded_rectangle([130, yy, W - 130, yy + 135], radius=40,
                                fill=GREEN if ok else BOX, outline=YEL if not dim else (90, 70, 130), width=5)
            ctext(d, f"{'ABC'[k]}) {o}", 60, yy + 32, WHITE if not dim else (150, 140, 180))
        yb = y0 + 3 * 175 + 60
        if kind == "conta":
            ctext(d, str(state["num"]), 150, yb - 40, YEL)
            ctas = ["Curte enquanto pensa", "Se inscreve pra mais", "Curte se acertar"]
            cta = ctas[(state["n"] - 1) % len(ctas)]
            # seta pulsando apontando pros botões do lado direito (curtir/seguir)
            pulse = 18 * math.sin(t_global * 2 * math.pi * 2)
            cy = yb + 200
            f = font(54)
            b = d.textbbox((0, 0), cta, font=f)
            tw = b[2] - b[0]
            x_end = W - 40 + pulse
            ax = x_end - 120
            d.text((ax - 30 - tw, cy - 40), cta, font=f, fill=WHITE)
            d.rectangle([ax - 10, cy - 14, ax + 50, cy + 14], fill=YEL)
            d.polygon([(ax + 40, cy - 48), (x_end, cy), (ax + 40, cy + 48)], fill=YEL)
        elif kind == "resp":
            for i, line in enumerate(wrap(q["fato"], 30)):
                ctext(d, line, 50, yb + i * 66, WHITE)
    ctext(d, HANDLE, 44, 1800, (180, 160, 220))
    return im

# ---------------- montagem ----------------
def build(roteiro, out):
    shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP)
    timeline = []  # (estado, dur, audio_eventos[(offset, array)])
    v = tts(roteiro["fala_gancho"], "g")
    timeline.append(({"kind": "gancho", "texto": roteiro["gancho"]}, len(v) / SR + 0.25, [(0, v)]))
    P = roteiro["perguntas"]
    for n, q in enumerate(P, 1):
        vq = tts(f"{q['pergunta']}", f"q{n}")
        st = {"q": q, "n": n, "tot": len(P)}
        timeline.append(({**st, "kind": "perg"}, len(vq) / SR + 0.2, [(0, vq)]))
        for num in (3, 2, 1):
            timeline.append(({**st, "kind": "conta", "num": num}, 0.8, [(0, tick())]))
        vr = tts(f"Letra {'ABC'[q['correta']]}! {q['fato']}", f"r{n}")
        timeline.append(({**st, "kind": "resp"}, len(vr) / SR + 0.5 + 0.35, [(0, ding()), (0.35, vr)]))
    vf = tts(roteiro["fala_final"], "f")
    timeline.append(({"kind": "final"}, len(vf) / SR + 0.6, [(0, vf)]))

    total = sum(t[1] for t in timeline)
    n = int(SR * total) + SR
    voice = np.zeros(n, np.float32)
    t0 = 0.0
    for st, dur, evs in timeline:
        for off, a in evs:
            s = int((t0 + off) * SR); voice[s:s + len(a)] += a[: n - s]
        t0 += dur
    mus = music(n / SR); mus = np.pad(mus, (0, max(0, n - len(mus))))[:n]
    mix = voice + mus
    mix = np.clip(mix / max(1.0, np.abs(mix).max()), -1, 1)
    wav = os.path.join(TMP, "mix.wav")
    with wave.open(wav, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())

    fdir = os.path.join(TMP, "frames"); os.makedirs(fdir)
    i, t0, cache = 0, 0.0, {}
    for st, dur, _ in timeline:
        nf = int(round((t0 + dur) * FPS)) - int(round(t0 * FPS))
        for k in range(nf):
            tg = (i / FPS)
            frame(st, tg, total).save(os.path.join(fdir, f"f{i:05d}.png"), compress_level=1)
            i += 1
        t0 += dur
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS),
                    "-i", os.path.join(fdir, "f%05d.png"), "-i", wav,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", out], check=True)
    shutil.rmtree(TMP, ignore_errors=True)
    return total

if __name__ == "__main__":
    r = json.load(open(sys.argv[1], encoding="utf-8"))
    print(f"duração: {build(r, sys.argv[2]):.1f}s")
