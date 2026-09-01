# Data Model: microcopy de segurança do Auto-Clicker

Esta feature não cria entidades persistentes nem altera o modelo de domínio.

## Elemento de apresentação

### `safety_text`

- Tipo: `QLabel` existente em `SettingsPage`.
- Fonte: literal estático pt-BR.
- Estilo esperado: cor `COLORS['text_secondary']`, fundo transparente, `font-size: 12px`, `setWordWrap(True)`.
- Invariantes: visível, não interativo, não afirma estado running/success, contido nos dois viewports oficiais.

## Estado funcional preservado

- `AutoClickerState`: `stopped`, `running`, `blocked_by_focus`, `failed`.
- `WindowFocusChecker`: fonte de verdade para foco e fail-closed quando indisponível.
- `autoclick_available`: capability que dirige o gating existente.
- Nenhum desses valores é alterado pela feature.

## Estados de copy

| Condição | Copy de segurança | Fonte de verdade |
| --- | --- | --- |
| Explicação permanente | linguagem neutra sobre foco e bloqueio | literal do QLabel |
| Jogo permitido em foco | motor pode clicar | `WindowFocusChecker`/engine |
| Fora do jogo | nenhum clique | estado `blocked_by_focus` e checker |
| Backend de automação indisponível | capability/status existente | `CapabilityState` |
