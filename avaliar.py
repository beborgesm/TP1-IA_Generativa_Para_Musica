# Mede, para cada ordem, quanto as músicas geradas copiam o corpus
import argparse
import random
import statistics
from collections import Counter

import corpus_dados
from gerar import gerar_peca, formatar_uso, BEATS_SECAO

ORDENS = (1, 2, 3, 4)
N = 6                                       # tamanho dos n-gramas da memorização
JANELA_REF = 100                            # notas por janela na referência (≈ seções A e B)


# Converte notas absolutas em transições relativas (intervalo, duração)
def estados(seq):
    return [(max(-12, min(12, b[0] - a[0])), round(b[1] * 12) / 12)
            for a, b in zip(seq, seq[1:])]


def gramas(seq):
    est = estados(seq)
    return [tuple(est[i:i + N]) for i in range(len(est) - N + 1)]


# Comprimento da maior subsequência contígua comum entre duas listas
def maior_trecho(a, b):
    melhor, anterior = 0, [0] * (len(b) + 1)
    for x in a:
        atual = [0] * (len(b) + 1)
        for j, y in enumerate(b, 1):
            if x == y:
                atual[j] = anterior[j - 1] + 1
                melhor = max(melhor, atual[j])
        anterior = atual
    return melhor


# Seções A e B da melodia (sem a repetição final de A)
def so_ab(melodia):
    return [(alt, dur) for alt, dur, t in melodia if t < 2 * BEATS_SECAO]


# Proporção de n-gramas da melodia gerada que existem no corpus
def memorizacao(melodia, corpus_gramas):
    g = gramas(so_ab(melodia))
    return sum(x in corpus_gramas for x in g) / max(len(g), 1)


# Maior trecho da melodia gerada idêntico a um trecho de uma única peça do corpus
def maior_copia(melodia, corpus_estados):
    est = estados(so_ab(melodia))
    return max(maior_trecho(est, c) for c in corpus_estados)


# Referência do acaso: janelas de uma peça real contra as outras peças reais
def referencia(corpus_estados):
    return [max(maior_trecho(c[i:i + JANELA_REF], o)
                for j, o in enumerate(corpus_estados) if j != k)
            for k, c in enumerate(corpus_estados)
            for i in range(0, len(c) - JANELA_REF, JANELA_REF)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-suporte", type=int, default=2)
    parser.add_argument("--num-sementes", type=int, default=30)
    args = parser.parse_args()
    sementes = range(1, args.num_sementes + 1)

    pecas = corpus_dados.carregar()
    sequencias = [[(x[0], x[1]) for x in melodia] for melodia, _ in pecas]
    corpus_gramas = {g for seq in sequencias for g in gramas(seq)}
    corpus_estados = [estados(seq) for seq in sequencias]

    ref = referencia(corpus_estados)
    print(f"min_suporte={args.min_suporte} sementes={len(sementes)}")
    print(f"referência (maior trecho comum entre peças reais diferentes): "
          f"média {statistics.mean(ref):.1f}, mediana {statistics.median(ref)}, máx {max(ref)}")
    print(f"{'ordem':>5s}  {'memorização':>12s}  "
          f"{'maior trecho em intervalos (média ± dp | mediana)':>50s}  "
          "uso de cada ordem (backoff)")
    for ordem in ORDENS:
        mems, trechos, uso = [], [], Counter()
        for semente in sementes:
            melodia, _, contagem = gerar_peca(pecas, ordem, args.min_suporte,
                                              random.Random(semente))
            mems.append(memorizacao(melodia, corpus_gramas))
            trechos.append(maior_copia(melodia, corpus_estados))
            uso += contagem
        trecho = (f"{statistics.mean(trechos):.1f} ± {statistics.stdev(trechos):.1f} | "
                  f"{statistics.median(trechos):.1f}")
        print(f"{ordem:5d}  {statistics.mean(mems):5.2f} ± {statistics.stdev(mems):4.2f}  "
              f"{trecho:>50s}  {formatar_uso(uso)}")


if __name__ == "__main__":
    main()