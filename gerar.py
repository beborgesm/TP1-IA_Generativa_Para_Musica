# Gera uma peça A-B-A para trio de cordas com cadeias de Markov e salva em MIDI
import random
import argparse
from collections import Counter, defaultdict
import pretty_midi

import corpus_dados

COMPASSOS_SECAO = 8
BEATS_COMPASSO = 4
BEATS_SECAO = COMPASSOS_SECAO * BEATS_COMPASSO
AMBITO = (62, 89)
ORDEM_BAIXO = 1
JANELA = corpus_dados.JANELA
JANELAS_SECAO = BEATS_SECAO // JANELA
TONICA = 0
ESCALA = (0, 2, 4, 5, 7, 9, 11)             # dó maior pois o corpus está transposto para dó


# Treina a matriz de transição entre notas do baixo (Cadeia de Markov)
def treinar_baixo(pecas, ordem):
    trans = defaultdict(list)
    for _, linha_baixo in pecas:
        for i in range(ordem, len(linha_baixo)):
            trans[tuple(linha_baixo[i - ordem:i])].append(linha_baixo[i])
    return trans


# Gera a linha de baixo (uma nota por janela), começando e terminando na tônica
def gerar_baixo(trans, n, rng):
    linha_baixo = [TONICA]
    while len(linha_baixo) < n:
        lista = trans.get(tuple(linha_baixo[-ORDEM_BAIXO:]))
        linha_baixo.append(rng.choice(lista) if lista else TONICA)
    linha_baixo[-1] = TONICA
    return linha_baixo


# Posição da nota da melodia em relação à nota do baixo
def contexto_baixo(altura, baixo):
    return (altura - baixo) % 12


# Acorde do acompanhamento: tríade diatônica com a nota do baixo na base (empilha terças da
# escala); nota do baixo cromática: tríade maior
def notas_do_acorde(nota_baixo):
    if nota_baixo not in ESCALA:
        return [nota_baixo, (nota_baixo + 4) % 12, (nota_baixo + 7) % 12]
    i = ESCALA.index(nota_baixo)
    return [ESCALA[i], ESCALA[(i + 2) % 7], ESCALA[(i + 4) % 7]]


# Treina o modelo melódico com suporte a backoff de ordem k
def treinar_melodia(pecas, ordem):
    tabelas = [defaultdict(list) for _ in range(ordem + 1)]
    so_metrica = defaultdict(list)
    for melodia, _ in pecas:
        estados = [(max(-12, min(12, melodia[i][0] - melodia[i - 1][0])), melodia[i][1])
                   for i in range(1, len(melodia))]
        for i in range(1, len(estados)):
            _, _, fase, forte, baixo = melodia[i + 1]
            metrica = (fase, forte)
            cb = contexto_baixo(melodia[i][0], baixo)
            for k in range(ordem + 1):
                if i - k >= 0:
                    tabelas[k][(tuple(estados[i - k:i]), metrica, cb)].append(estados[i])
            so_metrica[metrica].append(estados[i])
    return tabelas, so_metrica


# Busca os próximos candidatos melódicos aplicando backoff
def candidatos(modelo, historico, metrica, cb, ordem, min_suporte):
    tabelas, so_metrica = modelo
    for k in range(ordem, -1, -1):
        if len(historico) < k:
            continue
        lista = tabelas[k].get((tuple(historico[len(historico) - k:]), metrica, cb), [])
        if len(lista) >= min_suporte:
            return lista, k
    if so_metrica.get(metrica):
        return so_metrica[metrica], "metrica"
    return [(0, 1.0)], "padrao"


# Gera a sequência melódica condicionada ao baixo e respeitando a tessitura
def gerar_frase(modelo, ordem, min_suporte, linha_baixo, beats, inicio, rng, contagem):
    altura, historico, notas, t = inicio, [], [], 0.0
    while t < beats - 1e-6:
        fase = round((t % 1) * 12) / 12
        metrica = (fase, abs(t % BEATS_COMPASSO) < 1e-6)
        baixo = linha_baixo[min(int(t // JANELA), len(linha_baixo) - 1)]
        lista, origem = candidatos(modelo, historico, metrica,
                                   contexto_baixo(altura, baixo), ordem, min_suporte)
        contagem[origem] += 1
        dentro = [e for e in lista if AMBITO[0] <= altura + e[0] <= AMBITO[1]]
        if dentro:
            iv, dur = rng.choice(dentro)
        else:
            iv, dur = rng.choice(lista)
            iv = -iv
        altura += iv
        dur = min(dur, beats - t)
        notas.append((altura, dur, t))
        historico.append((iv, dur))
        t = round((t + dur) * 12) / 12
    return notas


# Força cadência final na tônica
def fechar_na_tonica(notas):
    alt, _, t = notas[-1]
    tonica = min((a for a in range(AMBITO[0], AMBITO[1] + 1) if a % 12 == 0),
                 key=lambda a: abs(a - alt))
    notas[-1] = (tonica, BEATS_SECAO - t, t)
    return notas


def gerar_secao(modelo, trans, ordem, min_suporte, rng, contagem):
    linha_baixo = gerar_baixo(trans, JANELAS_SECAO, rng)
    inicio = rng.choice([72, 76, 79])
    frase = gerar_frase(modelo, ordem, min_suporte, linha_baixo, BEATS_SECAO, inicio, rng, contagem)
    return fechar_na_tonica(frase), linha_baixo


# Constrói a estrutura completa da peça na forma A-B-A
def gerar_peca(pecas, ordem, min_suporte, rng):
    modelo = treinar_melodia(pecas, ordem)
    trans = treinar_baixo(pecas, ORDEM_BAIXO)
    contagem = Counter()
    a = gerar_secao(modelo, trans, ordem, min_suporte, rng, contagem)
    b = gerar_secao(modelo, trans, ordem, min_suporte, rng, contagem)

    melodia, linha_baixo = [], []
    for i, (mel, lb) in enumerate([a, b, a]):
        melodia += [(alt, dur, i * BEATS_SECAO + t) for alt, dur, t in mel]
        linha_baixo += lb
    return melodia, linha_baixo, contagem


def oitava_proxima(pc, ref):
    base = ref - ref % 12 + pc
    return min((base - 12, base, base + 12), key=lambda x: abs(x - ref))


# Realiza a linha de baixo (violoncelo) e a figuração (Alberti na seção A, arpejo na B)
def acompanhar(linha_baixo):
    baixos, figuracao = [], []
    for i, nota_baixo in enumerate(linha_baixo):
        t0 = JANELA * i
        pcs = notas_do_acorde(nota_baixo)
        baixo = oitava_proxima(nota_baixo, 43)
        meio = sorted(a for a in range(55, 70) if a % 12 in pcs and a > baixo + 2)
        baixos.append((baixo, float(JANELA), t0, 62))
        if len(meio) < 3:
            continue
        if i // JANELAS_SECAO == 1:
            padrao = [meio[0], meio[1], meio[2], meio[1]]
        else:
            padrao = [meio[0], meio[2], meio[1], meio[2]]
        for k, alt in enumerate(padrao):
            figuracao.append((alt, 0.5, t0 + 0.5 * k, 58 if k == 0 else 54))
    return baixos, figuracao


# Exporta a melodia e vozes de acompanhamento para arquivo MIDI
def salvar_midi(melodia, baixos, figuracao, nome_arquivo, bpm=96):
    midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    violino = pretty_midi.Instrument(program=40, name="Melodia")
    violoncelo = pretty_midi.Instrument(program=42, name="Baixo")
    viola = pretty_midi.Instrument(program=41, name="Figuracao")
    spb = 60.0 / bpm
    for alt, dur, t in melodia:
        vel = 92 if abs(t % BEATS_COMPASSO) < 1e-6 else 80 if abs(t % 1) < 1e-6 else 72
        violino.notes.append(pretty_midi.Note(velocity=vel, pitch=int(alt),
                                              start=t * spb, end=(t + dur * 0.98) * spb))
    for instrumento, notas in ((violoncelo, baixos), (viola, figuracao)):
        for alt, dur, t, vel in notas:
            instrumento.notes.append(pretty_midi.Note(velocity=vel, pitch=int(alt),
                                                      start=t * spb, end=(t + dur * 0.98) * spb))
    midi.instruments += [violino, violoncelo, viola]
    midi.write(nome_arquivo)


def formatar_uso(contagem):
    total = sum(contagem.values())
    itens = sorted(contagem.items(), key=lambda x: str(x[0]))
    return ", ".join(f"{'k=' if isinstance(k, int) else ''}{k}: {v / total:.0%}"
                     for k, v in itens)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ordem", type=int, default=2, help="ordem da cadeia da melodia")
    parser.add_argument("--min-suporte", type=int, default=2,
                        help="ocorrências mínimas de um contexto antes do backoff")
    parser.add_argument("--semente", type=int, default=1)
    args = parser.parse_args()

    rng = random.Random(args.semente)
    pecas = corpus_dados.carregar()
    melodia, linha_baixo, contagem = gerar_peca(pecas, args.ordem, args.min_suporte, rng)
    baixos, figuracao = acompanhar(linha_baixo)

    nome = f"musica_ordem{args.ordem}_seed{args.semente}.mid"
    salvar_midi(melodia, baixos, figuracao, nome)
    print("Gerado:", nome, "-", len(melodia), "notas na melodia,",
          len(baixos) + len(figuracao), "no acompanhamento")
    print("Uso de cada ordem (backoff):", formatar_uso(contagem))


if __name__ == "__main__":
    main()