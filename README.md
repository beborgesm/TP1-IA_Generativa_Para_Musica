# Composição algorítmica com cadeias de Markov

TP1 de DCC831 (IA Generativa para Música, UFMG). Método: **cadeias de Markov aprendidas de um
corpus real** (quartetos de cordas de Mozart, Haydn e Beethoven, do `music21.corpus`,
transpostos para Dó maior; só trechos em 4/4). Restrição estilística: quarteto de cordas
clássico, em forma ternária A–B–A (8 compassos por seção, 4/4, 96 bpm). A saída de cada
execução é um arquivo MIDI para trio de cordas (violino, viola e violoncelo).

O resumo em formato ISMIR está em [`relatorio/Relatorio_TP1.pdf`](relatorio/Relat%C3%B3rio_TP1.pdf).

## Instalação

Testado com Python 3.13, music21 10.5.0 e pretty_midi 0.2.11.

    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt

A primeira execução lê o corpus pelo music21 (~25 s) e guarda o resultado em `.cache/`. **Se
alterar `corpus_dados.py`, apague a pasta `.cache/`** para o corpus ser reprocessado.

Para sintetizar áudio (opcional, só para audição) são necessários FluidSynth, ffmpeg e um
SoundFont livre (usamos o GeneralUser GS). No macOS: `brew install fluid-synth ffmpeg`.

## Uso

    python gerar.py --ordem 2 --semente 27        # grava musica_ordem2_seed27.mid na pasta atual
    python avaliar.py                             # tabela de memorização, min-suporte 2
    python avaliar.py --min-suporte 1             # mesma tabela com min-suporte 1

Hiperparâmetros de `gerar.py`:

| Opção | Padrão | Efeito |
|---|---|---|
| `--ordem` | 2 | ordem da cadeia da melodia (quantos estados anteriores formam o contexto) |
| `--min-suporte` | 2 | ocorrências mínimas de um contexto antes do backoff para uma ordem menor |
| `--semente` | 1 | semente do sorteio; com a mesma configuração, sementes diferentes dão peças diferentes |

A ordem da cadeia do baixo é fixa (`ORDEM_BAIXO = 1` em `gerar.py`). A mesma ordem, semente e
`--min-suporte` sempre geram o mesmo arquivo.

## Reproduzir os resultados

**Músicas entregues** (pasta `musicas/`, arquivos `.mid` e `.mp3`). Variam ordem e semente:

| Arquivo | Ordem | Semente |
|---|---|---|
| `musica_ordem2_seed27` | 2 | 27 |
| `musica_ordem3_seed1` | 3 | 1 |
| `musica_ordem1_seed44` | 1 | 44 |

Para regerar os `.mid` (a partir da raiz do repositório):

    mkdir -p musicas && cd musicas
    python ../gerar.py --ordem 2 --semente 27
    python ../gerar.py --ordem 3 --semente 1
    python ../gerar.py --ordem 1 --semente 44

Para sintetizar o áudio de cada `.mid` (exemplo para a primeira; o SoundFont é o
`GeneralUser-GS.sf2`, baixado de https://schristiancollins.com/generaluser.php e guardado fora
do repositório):

    fluidsynth -ni -F musica_ordem2_seed27.wav -r 44100 GeneralUser-GS.sf2 musica_ordem2_seed27.mid
    ffmpeg -i musica_ordem2_seed27.wav -af "loudnorm=I=-16:TP=-1.5:LRA=11" -codec:a libmp3lame -q:a 2 musica_ordem2_seed27.mp3

**Tabela do resumo** (`python avaliar.py`, 30 sementes por ordem, ordens 1 a 4): mostra a
memorização (fração de sequências de 6 estados da melodia gerada que existem no corpus), o
maior trecho copiado de uma única peça do corpus (em estados consecutivos), a referência entre
peças reais e a taxa de uso de cada ordem pelo backoff. O número de sementes pode ser mudado
com `--num-sementes`.

## Modelo

- **Baixo:** cadeia de Markov de ordem 1 sobre a nota do baixo (classe de altura relativa à
  tônica) a cada 2 tempos, aprendida do corpus (nota mais longa do violoncelo na janela;
  nas janelas sem violoncelo, usam-se as demais vozes). Começa e termina na tônica.
- **Melodia:** cadeia de Markov de ordem `--ordem` sobre estados (intervalo, duração) do
  violino I, condicionada à fase métrica, ao primeiro tempo do compasso e ao intervalo entre a
  nota atual e o baixo vigente. Probabilidades por contagem no corpus, com backoff para ordens
  menores quando o contexto tem menos de `--min-suporte` ocorrências.
- **Convenções fixas (não aprendidas):** forma A–B–A (o retorno de A repete a primeira seção);
  a última nota de cada seção é a tônica; altura de partida de cada seção sorteada entre Dó, Mi
  e Sol; candidatos fora do âmbito do violino (MIDI 62–89) são descartados (o salto é invertido
  se nenhum couber); o acompanhamento é um padrão fixo sobre o baixo sorteado (tríade
  diatônica de Dó maior, em baixo de Alberti na seção A e arpejo na B).
- **Saída:** MIDI com violino (melodia), violoncelo (baixo) e viola (figuração).

## Estrutura

    gerar.py          geração das peças (cadeias de Markov, acompanhamento, MIDI)
    corpus_dados.py   extração do corpus (melodia e baixo) do music21, com cache
    avaliar.py        medidas de cópia do corpus por ordem
    musicas/          3 peças geradas (.mid e .mp3)
    relatorio/        resumo em formato ISMIR (Relatório_TP1.pdf)
    requirements.txt  dependências

## Uso de IA

Seguindo as regras do enunciado, utilizei o Google Gemini como apoio consultivo, na validação de ideias teóricas, no desenvolvimento do script auxiliar de testes e na revisão do artigo. A implementação central do método generativo e a escrita do resumo foram feitas por mim. O uso dividiu-se nas seguintes frentes:

- **Discussão teórica e modelagem musical:**
  - **Tratamento de notas repetidas e dinâmica harmônica:** conversamos sobre o problema de repetições excessivas na melodia e validamos a ideia de que um chão harmônico estático travava o contexto vertical da cadeia; discutimos como extrair o baixo polifônico para destravar as transições melódicas em ordens mais altas ($k \ge 1$).
  - **Representação e invariância:** discutimos a modelagem de estados usando intervalos relativos $(\Delta \text{pitch}, \text{duração})$ limitados a $\pm 12$ semitons em vez de notas absolutas, garantindo invariância à transposição ou tessitura.
  - **Textura instrumental clássica:** validação de convenções de estilo clássico, como o uso do baixo Alberti canônico na viola durante a seção A, arpejos de preenchimento na seção B, condução estrutural da tônica no violoncelo e cadências conclusivas nas seções da forma A–B–A.
  - **Humanização da síntese MIDI:** discussão sobre diferenciação de dinâmica métrica (velocities para tempos fortes, médios e fracos) e folga de articulação de arco (gate ratio) para que os instrumentos não soassem mecânicos.

- **Código auxiliar de avaliação e benchmarking (`avaliar.py`):**
  - Me ajudou a estruturar o algoritmo de programação dinâmica para calcular a maior subsequência contígua comum (LCS) e a extração de $N$-gramas.
  - Discutimos a escolha de 6 passos ($N=6$) para evitar falsos positivos de escalas curtas e a medição restrita às seções A e B para não inflar as contagens com a repetição de A.
  - Validação da ideia de criar uma linha de base (*baseline*) cruzando peças reais diferentes do próprio corpus, medindo o limiar de coincidência natural do Classicismo.
  - Aporte na agregação estatística (médias, medianas e desvio padrão) e na depuração de incompatibilidades de tuplas durante a execução. A refatoração enxuta final, a lógica de amostragem por janelas e a integração foram finalizadas por mim.

- **Formatação e escrita científica (ISMIR):**
  - Ajuda para localizar e configurar o template oficial do ISMIR 2026 no Overleaf.
  - Planejamento de densidade para encaixar todas as seções, formalização matemática e tabelas dentro do limite rígido de 2 páginas de conteúdo.
  - Revisão e sugestões de clareza/concisão para parágrafos da Introdução, Trabalhos Relacionados, Método e interpretação dos resultados empíricos.

A concepção da arquitetura, a implementação dos scripts principais (`corpus_dados.py` e `gerar.py`) e a redação definitiva do resumo científico são de minha autoria.

- **Link da conversa:** 
https://share.gemini.google/ghlLLD5D713f