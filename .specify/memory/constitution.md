<!--
## Sync Impact Report
- Version change: 1.0.0 → 1.1.0
- Emenda: 2026-08-31
- Razão: ampliar formalmente o Mouse Hub de controlador centrado no G403 para motor
  local de controle e automação de entrada (mouse + teclado), preservando o G403
  como primeiro adapter de hardware e definindo fronteiras contra RPA semântico,
  gerenciamento universal de periféricos e captura contínua de teclado.
- Princípio adicionado: IX. Entrada Componível e Fronteiras de Responsabilidade.
- Princípios ajustados: III e V para incluir backends de input e automação.
- Restrições de segurança ajustadas: captura de teclado deve ser explícita,
  observável, delimitada e cancelável; keylogging contínuo não pertence ao produto.
- Documentação relacionada: README.md, AGENTS.md, docs/ARCHITECTURE.md.
-->

# Mouse Hub Constitution

## Core Principles

### I. Correção de Hardware em Primeiro Lugar
Toda operação que toque hardware suportado (atualmente o Logitech G403 HERO via
HID++, udev e endpoint hidraw) MUST ter sucesso confirmado por evidência do
protocolo antes de ser reportada como sucesso. Falha de hardware NÃO MUST ser
convertida em sucesso visual, em estado persistido ou em silêncio. A identidade do
dispositivo é sempre validada; a descoberta de endpoint não depende de ordem de
enumeração nem de `/dev/hidraw0`.

### II. Honestidade de Estado (UI Não Simula)
A UI projeta o estado do core e NÃO é fonte de verdade sobre hardware. Capacidade
não confirmada MUST aparecer como indisponível com a causa visível (ex.: polling
rate sem capacidade confirmada; automações X11 indisponíveis em Wayland). Estados
conhecidos, desconhecidos e de falha são visualmente distintos e não devem ser
trocados por indicadores ambíguos.

### III. Fakes no CI, Hardware Fora (NON-NEGOTIABLE)
Nada que dependa de hardware físico, udev, XTest/XRecord, backends de input ou
sessão gráfica real pode depender desse ambiente para o CI passar. Código novo que
toque hardware/input MUST ter caminho fakeável (`tests/fakes.py`) e teste
determinístico correspondente. Testes com fakes provam comportamento do software;
não são evidência de validação física do G403 nem de sessão X11 real quando esse
detalhe é relevante.

### IV. Regressão Com Teste Junto do Fix
Toda correção de bug chega com teste que falha sem a mudança e passa com ela.
Regressões conhecidas (ex.: busy-loop do scheduler) têm teste dedicado e não devem
ser mascaradas por thresholds enfraquecidos.

### V. Regras de Domínio Somente no Core (NON-NEGOTIABLE)
Estado, perfis, configuração, descoberta, DPI, sensibilidade, polling e regras de
automação/input vivem exclusivamente em `mouse_hub/core/`. A plataforma fornece
mecanismos e adapters; a UI projeta estado e comandos. Duplicar regra de domínio na
UI (`app/`) ou na camada de plataforma (`mouse_hub/platform/`) é bug de arquitetura.
Constantes de domínio MUST vir de `mouse_hub/core/constants.py` quando aplicável —
sem limites hardcoded em outro lugar. O servidor web legado não volta.

### VI. Menor Mudança Completa
Cada linha de mudança rastreia até uma issue ou spec. Sem refatoração drive-by,
sem reformatação de código alheio, sem dependência nova para problema trivial.
Legibilidade e testes valem mais que economia de tokens. A UI PyQt5 permanece
fixada em 5.15.11 no CI.

### VII. Verificação Dupla (Software e Realidade)
Toda claim de comportamento deve distinguir: (a) evidência de software (testes
determinísticos, benchmarks offscreen) e (b) evidência física (medição no G403
real, sessão X11 real, hardware de referência). Medidas de outras máquinas são
rotuladas como medidas daquele ambiente. Nenhum resultado é descrito como
fisicamente validado sem medição no hardware real.

### VIII. UX Honesta e Consistente
Microcopy, ícones e estados seguem o padrão editorial do resto da UI (pt-BR
consistente, sem mistura de idiomas em headings). O usuário final não precisa de
terminal para fluxos suportados (ex.: permissão HID via polkit). Exposição técnica
interna (backends, caminhos de máquina) não aparece na UI voltada ao usuário nem
em artefatos públicos.

### IX. Entrada Componível e Fronteiras de Responsabilidade (NON-NEGOTIABLE)
O Mouse Hub é um motor local de controle e automação de entrada para mouse e
teclado, com hardware baseado em capabilities explícitas. Features como
auto-clicker, macros, hotkeys e perfis SHOULD compor primitivas comuns de input,
timing, sequência e repetição em vez de criar emissores paralelos.

Suporte genérico de input NÃO implica gerenciamento universal de periféricos:
firmware, RGB, polling ou recursos proprietários só entram com adapter/capability
explicitamente implementado. O G403 é o primeiro adapter concreto, não a definição
do produto.

O Mouse Hub executa ações de entrada, mas NÃO interpreta semanticamente aplicações
nem decide sozinho o que clicar. OCR, visão de tela, RPA de propósito geral e
tomada autônoma de decisão sobre aplicações pertencem a camadas superiores.
Captura de teclado/cliques só pode ocorrer em modos explícitos, observáveis,
delimitados e canceláveis; keylogging global contínuo ou silencioso é incompatível
com esta constituição.

## Restrições de Plataforma e Segurança

- Alvo: Linux Mint, sessão X11 para automações atuais (XTest/XRecord/libinput); DPI
  físico via HID++ funciona independente da sessão gráfica.
- Permissões HID via regra udev `0660` + grupo `plugdev`; nunca `chmod 666` em
  `/dev/hidrawX` como fluxo normal; em ambiente sem permissão, degradação elegante,
  nunca crash.
- Emissão de teclado e captura de teclado são capabilities distintas. Uma não pode
  habilitar silenciosamente a outra.
- Captura global contínua/oculta do que o usuário digita é proibida. Gravação de
  macros/hotkeys exige lifecycle explícito e visível, com cancelamento confiável.
- Configuração e dados em diretórios XDG; migração do layout legado é não
  destrutiva; config corrompida não é sobrescrita silenciosamente.
- Sem busy-wait, sem subprocesso recorrente em idle; metas de performance conforme
  `docs/performance/metodologia.md`.

## Fluxo de Trabalho e Qualidade

- Branch + PR sempre (`fix/<tema>`, `feat/<tema>`, `chore/<tema>`); commits
  convencionais em inglês; nunca push direto na `main`.
- PR vinculada à issue/spec quando houver uma correspondente, com problema,
  abordagem, testes executados e riscos; quem implementa não faz merge (revisão do
  mantenedor).
- Um PR só está pronto quando os 2 jobs do CI passam (test + ui_smoke); o estado
  reportado vem das checks reais, nunca presumido.
- Desenvolvimento Dirigido por Especificação (Spec Kit): features relevantes partem
  de spec em `specs/` (`/speckit-specify` → plan → tasks → implement → converge);
  mudanças triviais/documentais podem seguir direto para PR, desde que preservem
  os princípios acima.
- Idioma: pt-BR para comentários, docstrings, issues, PRs e specs; identificadores
  de código em inglês.

## Governance

- Esta constituição é a fonte máxima de princípios do projeto; AGENTS.md detalha o
  dia a dia operacional e MUST permanecer compatível com ela.
- Emendas exigem: descrição da mudança, bump de versão semântica (MAJOR = remoção
  ou redefinição incompatível de princípio; MINOR = novo princípio ou expansão
  material; PATCH = clarificação), e registro no Sync Impact Report do arquivo.
- Todo PR/review verifica compliance com estes princípios; conflito entre PR e
  constituição resolve-se em favor da constituição, e o PR precisa ser ajustado.
- Revisão de compliance ocorre a cada release MINOR/MAJOR do produto.

**Version**: 1.1.0 | **Ratified**: 2026-08-28 | **Last Amended**: 2026-08-31