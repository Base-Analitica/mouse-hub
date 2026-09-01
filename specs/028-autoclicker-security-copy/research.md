# Research: microcopy de segurança do Auto-Clicker

## Contrato observado

- `SettingsPage` monta o grupo `Auto-Clicker — Segurança` e o `safety_text` em `app/mouse_hub_app.py:2685-2696`.
- A copy atual mistura garantia operacional com detalhes de backend: `X11`, cache de `500 ms` e `TTL`.
- O stylesheet atual aplica `COLORS['mc_green']` ao parágrafo inteiro, embora o bloco seja explicativo e permanente.
- O motor em `mouse_hub/core/automation/autoclicker.py` consulta foco antes de emitir cada clique e muda para `blocked_by_focus` quando a janela permitida não está focada.
- A UI já comunica a mesma garantia no tooltip do botão e nos estados do motor.

## Decisão

Manter a garantia verificável em linguagem de usuário e retirar o mecanismo interno da superfície operacional:

> O auto-clicker só funciona quando Minecraft/Lunar Client está em foco. O app verifica a janela ativa antes de clicar. Fora do jogo, nenhum clique é realizado.

Aplicar `COLORS['text_secondary']` ao QLabel. Nenhuma mudança no core ou na plataforma é necessária.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Copy prometer comportamento além do motor | usar somente foco, verificação antes do clique e bloqueio fora do jogo, já cobertos pelo core |
| Remoção do verde esconder estado real | o verde permanece em estados/capabilities, somente o corpo explicativo fica neutro |
| Quebra de layout small | teste de geometria nos dois viewports e screenshots oficiais |
| PRs concorrentes alterarem a mesma área | fechar #82 e #83 no mesmo branch/PR, sem incorporar outros issues |

## Fora de escopo

- Motor, checker, serviço, cache interno, X11/XTest/XRecord, capability gating, persistência, botão e estados reais.
