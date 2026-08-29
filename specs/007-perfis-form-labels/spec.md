# Feature Specification: Formulário de Perfis com labels persistentes

**Feature Branch**: `fix/profile-form-labels`

**Created**: 2026-08-29

**Status**: Draft

**Input**: User description: "Issue #114 — o formulário de Perfis não
tem labels persistentes: nome depende só de placeholder (some ao
digitar), `800 DPI` e `50%` exigem dedução. Placeholder não substitui
label."

## Correção

- Labels persistentes **acima** de cada campo: "Nome do perfil", "DPI",
  "Sensibilidade" — legíveis antes, durante e depois da edição.
- Unidades (` DPI`, `%`) permanecem como sufixo nos spinboxes —
  informação complementar, não único identificador.
- `accessibleName` dos campos corresponde aos labels (nome inclui o
  placeholder como dica complementar).
- Layout compacto preservado: label em linha própria (row 0/1), campos
  nas linhas seguintes; labels legíveis em 760×560.

## Acceptance Criteria

- três campos identificáveis quando preenchidos/focados;
- relação label → campo clara (proximidade vertical);
- labels legíveis em 760×560;
- accessible names correspondem;
- screenshots desktop/small regeneradas; CI verde.

## Principles Check

| Princípio | Aplicação |
| --- | --- |
| UX honesta | form autoexplicativo sem dedução |
| Menor mudança completa | 3 QLabel + setAccessibleName |
| Craft responsivo | labels em 760×560 sem estourar viewport |
| Dupla verificação | testes de presença + geometria |
