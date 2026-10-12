# Extrai do music21 a melodia e o baixo dos quartetos usados no treino, com cache local
import os
import pickle
from collections import defaultdict
from music21 import corpus

DIR_CACHE = os.path.join(os.path.dirname(__file__), ".cache")
JANELA = 2
MIN_COMPASSOS = 24

QUARTETOS = (
    [f"mozart/k{k}/movement{m}" for k, ms in
     {155: 3, 156: 4, 458: 4, 80: 4}.items() for m in range(1, ms + 1)]
    + [f"haydn/opus1no1/movement{m}" for m in range(1, 6)]
    + [f"haydn/opus74no1/movement{m}" for m in range(1, 5)]
    + [f"beethoven/opus18no1/movement{m}" for m in range(1, 5)]
    + [f"beethoven/opus59no{n}/movement{m}" for n in (1, 2, 3) for m in range(1, 5)]
    + ["beethoven/opus74"]
    + ["beethoven/opus18no3", "beethoven/opus18no4", "beethoven/opus18no5"]
)


def _tonica(obra):
    tom = obra.analyze("key")
    return tom.tonic.pitchClass, tom.mode


# Isola trechos contínuos em fórmula 4/4
def _trechos_44(obra):
    formulas = [ts.ratioString for ts in obra.recurse().getElementsByClass("TimeSignature")]
    if set(formulas) <= {"4/4"}:
        return [obra]
    trechos, ini, fim = [], None, None
    for c in obra.parts[0].getElementsByClass("Measure"):
        if c.timeSignature is not None:
            if ini is not None and fim - ini >= MIN_COMPASSOS:
                trechos.append(obra.measures(ini, fim))
            ini = c.number if c.timeSignature.ratioString == "4/4" else None
        if ini is not None:
            fim = c.number
    if ini is not None and fim - ini >= MIN_COMPASSOS:
        trechos.append(obra.measures(ini, fim))
    return trechos


# Nota do baixo em cada janela de 2 tempos, relativa à tônica: a mais longa da voz mais grave
# (violoncelo); se ele pausa na janela, a mais longa entre as outras vozes
def _extrair_baixo(obra, tonica):
    grave, outras = defaultdict(lambda: defaultdict(float)), defaultdict(lambda: defaultdict(float))
    for k, parte in enumerate(obra.parts):
        alvo = grave if k == len(obra.parts) - 1 else outras
        for n in parte.flatten().notes:
            ini, fim = float(n.offset), float(n.offset + n.quarterLength)
            for j in range(int(ini // JANELA), int((fim - 1e-6) // JANELA) + 1):
                dur = min(fim, (j + 1) * JANELA) - max(ini, j * JANELA)
                if dur > 0:
                    for p in n.pitches:
                        alvo[j][(p.pitchClass - tonica) % 12] += dur
    janelas = set(grave) | set(outras)
    linha_baixo, anterior = [], None
    for j in range(max(janelas) + 1 if janelas else 0):
        pesos = grave.get(j) or outras.get(j)
        if pesos:
            anterior = max(pesos, key=pesos.get)
        linha_baixo.append(anterior)
    return [b for b in linha_baixo if b is not None]


# Extrai a linha do Violino I transposta para Dó maior com contexto métrico
def _extrair_melodia(obra, tonica, linha_baixo):
    unicas, vistos = [], set()
    for n in obra.parts[0].flatten().notes:
        if n.quarterLength < 0.25:
            continue
        off = float(n.offset)
        if off in vistos:
            continue
        vistos.add(off)
        altura = n.pitch.midi if n.isNote else n.pitches[-1].midi
        unicas.append((off, altura, float(n.beat)))
    passos = -tonica if tonica <= 6 else 12 - tonica
    seq = []
    for i, (off, alt, beat) in enumerate(unicas[:-1]):
        dur = round(min(unicas[i + 1][0] - off, 3.0) * 12) / 12
        j = int(off // JANELA)
        if dur <= 0 or j >= len(linha_baixo):
            continue
        fase = round(((beat - 1) % 1) * 12) / 12
        seq.append((alt + passos, dur, fase, abs(beat - 1) < 1e-6, linha_baixo[j]))
    return seq


# Carrega o dataset de treino processado ou lê do cache local
def carregar():
    os.makedirs(DIR_CACHE, exist_ok=True)
    arq = os.path.join(DIR_CACHE, "quartetos.pkl")
    if os.path.exists(arq):
        with open(arq, "rb") as f:
            return pickle.load(f)

    pecas = []
    for nome in QUARTETOS:
        try:
            trechos = _trechos_44(corpus.parse(nome))
        except Exception as e:
            print("pulando", nome, e)
            continue
        for trecho in trechos:
            ton, modo = _tonica(trecho)
            if modo != "major":
                continue
            linha_baixo = _extrair_baixo(trecho, ton)
            melodia = _extrair_melodia(trecho, ton, linha_baixo)
            if len(melodia) > 50 and len(linha_baixo) > 8:
                pecas.append((melodia, linha_baixo))
                print("ok", nome, len(melodia), "notas", len(linha_baixo), "notas de baixo")

    with open(arq, "wb") as f:
        pickle.dump(pecas, f)
    return pecas