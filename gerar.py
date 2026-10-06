import random
from collections import defaultdict
from music21 import corpus
import pretty_midi

ORDEM = 2
SEMENTE = 1
NUM_CORAIS = 40
BEATS_TOTAIS = 128   # 32 compassos de 4/4 (1 beat = 1 semínima)

def carregar_melodias():
    melodias = []
    # corais numerados de 1 a NUM_CORAIS (numeração Riemenschneider)
    for coral in corpus.chorales.Iterator(1, NUM_CORAIS):
        soprano = coral.parts[0]          # a primeira voz é o soprano
        notas = soprano.flatten().notes
        melodias.append(notas)
    return melodias


def para_estados(notas):
    estados = []
    for n in notas:
        if n.isNote:                       # ignora acordes, caso apareçam
            estados.append((n.pitch.midi, float(n.quarterLength)))
    return estados


def treinar(melodias, ordem):
    transicoes = defaultdict(list)
    for notas in melodias:
        estados = para_estados(notas)
        for i in range(len(estados) - ordem):
            contexto = tuple(estados[i:i + ordem])
            proximo = estados[i + ordem]
            transicoes[contexto].append(proximo)
    return transicoes


def gerar(transicoes, ordem, beats_totais):
    contextos = list(transicoes.keys())
    melodia = list(random.choice(contextos))   # começa com um trecho real
    beats = sum(dur for _, dur in melodia)

    while beats < beats_totais:
        contexto = tuple(melodia[-ordem:])
        if contexto not in transicoes:         # beco sem saída
            melodia.extend(random.choice(contextos))
            beats = sum(dur for _, dur in melodia)
            continue
        proximo = random.choice(transicoes[contexto])
        melodia.append(proximo)
        beats += proximo[1]

    return melodia


def salvar_midi(melodia, nome_arquivo, bpm=90):
    midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    piano = pretty_midi.Instrument(program=0)
    tempo = 0.0
    seg_por_beat = 60.0 / bpm
    for altura, duracao in melodia:
        fim = tempo + duracao * seg_por_beat
        piano.notes.append(pretty_midi.Note(velocity=80, pitch=altura,
                                            start=tempo, end=fim))
        tempo = fim
    midi.instruments.append(piano)
    midi.write(nome_arquivo)


if __name__ == "__main__":
    random.seed(SEMENTE)
    melodias = carregar_melodias()
    transicoes = treinar(melodias, ORDEM)
    melodia = gerar(transicoes, ORDEM, BEATS_TOTAIS)
    salvar_midi(melodia, f"musica_ordem{ORDEM}_seed{SEMENTE}.mid")
    print("Gerado:", len(melodia), "notas")