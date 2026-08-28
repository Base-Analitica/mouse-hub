<!--
## Sync Impact Report
- Version change: (novo) → 1.0.0
- Ratificação: 2026-08-28 (adoção inicial junto com a instalação do Spec Kit v1.0.1)
- Princípios derivados de: AGENTS.md (regras para agentes), README.md (prioridades
  declaradas de contribuição) e histórico de issues/PRs do projeto
- Princípios adicionados: 8 (correção de hardware, honestidade de estado, fakes no CI,
  regressão com fix, core como única fonte de domínio, menor mudança completa,
  verificação dupla, UX honesta)
- Seções adicionadas: Restrições de Plataforma e Segurança; Fluxo de Trabalho e
  Qualidade; Governança
- Seções removidas: nenhuma
- TODOs adiados: nenhum
-->

# Mouse Hub Constitution

## Core Principles

### I. Correção de Hardware em Primeiro Lugar
Toda operação que toque no Logitech G403 HERO (HID++, udev, endpoint hidraw) MUST
ter sucesso confirmado por evidência do protocolo antes de ser reportada como
sucesso. Falha de hardware NÃO MUST ser convertida em sucesso visual, em estado
persistido ou em silêncio. A identidade do dispositivo é sempre validada; a
descoberta de endpoint não depende de ordem de enumeração nem de `/dev/hidraw0`.

### II. Honestidade de Estado (UI Não Simula)
A UI projeta o estado do core e NÃO é fonte de verdade sobre hardware. Capacidade
não confirmada MUST aparecer como indisponível com a causa visível (ex.: polling
rate sem capacidade confirmada; automações X11 indisponíveis em Wayland). Estados
conhecidos, desconhecidos e de falha são visualmente distintos e não devem ser
trocados por indicadores ambíguos.

### III. Fakes no CI, Hardware Fora (NON-NEGOTIABLE)
Nada que dependa do mouse físico, udev, XTest/XRecord ou sessão X11 real pode
depender de hardware para o CI passar. Código novo que toque hardware MUST ter
caminho fakeável (`tests/fakes.py`) e teste determinístico correspondente. Testes
com fakes provam comportamento do software; não são evidência de validação física
do G403 nem de sessão X11 real quando esse detalhe é relevante.

### IV. Regressão Com Teste Junto do Fix
Toda correção de bug chega com teste que falha sem a mudança e passa com ela.
Regressões conhecidas (ex.: busy-loop do scheduler) têm teste dedicado e não devem
ser mascaradas por thresholds enfraquecidos.

### V. Regras de Domínio Somente no Core (NON-NEGOTIABLE)
DPI, sensibilidade, perfis, polling, configuração e descoberta vivem exclusivamente
em `mouse_hub/core/`. Lógica de domínio na UI (`app/`) ou na camada de plataforma
(`mouse_hub/platform/`) é bug de arquitetura. Constantes de domínio MUST vir de
`mouse_hub/core/constants.py` — sem limites hardcoded em outro lugar. O servidor
web legado não volta.

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

## Restrições de Plataforma e Segurança

- Alvo: Linux Mint, sessão X11 para automações (XTest/XRecord/libinput); DPI físico
  via HID++ funciona independente da sessão gráfica.
- Permissões HID via regra udev `0660` + grupo `plugdev`; nunca `chmod 666` em
  `/dev/hidrawX` como fluxo normal; em ambiente sem permissão, degradação elegante,
  nunca crash.
- Configuração e dados em diretórios XDG; migração do layout legado é não
  destrutiva; config corrompida não é sobrescrita silenciosamente.
- Sem busy-wait, sem subprocesso recorrente em idle; metas de performance conforme
  `docs/performance/metodologia.md`.

## Fluxo de Trabalho e Qualidade

- Branch + PR sempre (`fix/<tema>`, `feat/<tema>`, `chore/<tema>`); commits
  convencionais em inglês; nunca push direto na `main`.
- PR vinculada à issue/spec com problema, abordagem, testes executados e riscos;
  quem implementa não faz merge (revisão do mantenedor).
- Um PR só está pronto quando os 2 jobs do CI passam (test + ui_smoke); o estado
  reportado vem das checks reais, nunca presumido.
- Desenvolvimento Dirigido por Especificação (Spec Kit): features relevantes partem
  de spec em `specs/` (`/speckit-specify` → plan → tasks → implement → converge);
  mudanças triviais (microcopy, P3) podem seguir direto de issue para PR, desde que
  preservem os princípios acima.
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

**Version**: 1.0.0 | **Ratified**: 2026-08-28 | **Last Amended**: 2026-08-28
