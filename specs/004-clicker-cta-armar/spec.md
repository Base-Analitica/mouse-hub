# Feature Specification: CTA do Auto-Clicker comunica armar/aguardar

**Feature Branch**: `fix/clicker-cta-armar`

**Created**: 2026-08-29

**Status**: Draft

**Input**: User description: "Issue #107 — banner vermelho 'Minecraft não
detectado' e CTA roxo 'Iniciar Auto-Clicker' comunicam instruções
opostas. O usuário não sabe se clicar é inválido, arma o clicker ou
inicia algo bloqueado."

## Contrato funcional real (sem inventar comportamento)

O motor (core, `AutoClickerEngine`) AO INICIAR sem jogo em foco entra em
`BLOCKED_BY_FOCUS`: ligado, aguardando a janela permitida, cliques
suprimidos. Logo o comportamento suportado é **"armar e aguardar"** —
a correção é renomear/comunicar, NÃO desabilitar o CTA (o focus-gating
permanece intacto e nenhum clique acontece fora do jogo).

## User Stories

### User Story 1 — Banner e CTA contam a mesma história (P1)

Com Minecraft ausente e motor desligado, o CTA diz "Armar Auto-Clicker
(aguardando o jogo)" e o sub-status explica o efeito ("Ao armar, o motor
aguarda o jogo em foco para clicar"). Com o jogo em foco, o CTA volta a
"Iniciar Auto-Clicker".

### User Story 2 — Estados distintos (P1)

`stopped+sem jogo` (Armar), `stopped+com jogo` (Iniciar), `blocked`
(Aguardando jogo em foco… / Parar), `running` (Ativo / Parar) e `failed`
(erro) têm representações distintas.

### Edge Cases

- Página renderizada sem serviço de janela (testes/captura): trata foco
  como não detectado — default seguro, comunica armar.
- Render inicial imediato no `_build`: o primeiro paint já é honesto,
  sem esperar o tick de 1 s do timer.

## Acceptance Criteria

- usuário sabe o que acontecerá antes de clicar;
- focus-gating inalterado (sem clique fora do jogo);
- desktop e small com a mesma semântica;
- testes cobrem Minecraft ausente vs detectado;
- screenshots atualizadas; CI verde.

## Principles Check

| Princípio | Aplicação |
| --- | --- |
| Honestidade de estado | CTA = ação real do contrato (armar/iniciar/parar) |
| UX honesta | sub-status explica o efeito de armar |
| Domain no core | nenhum comportamento novo inventado; copy segue o motor |
| Menor mudança completa | constantes + render inicial; gating intacto |
