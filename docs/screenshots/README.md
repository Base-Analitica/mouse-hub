# Screenshots do Mouse Hub

**Estas imagens devem estar SEMPRE atualizadas com a main.**

Regenerar (determinístico — offscreen + fakes, hardware nunca necessário):

```bash
python3 scripts/capture_screenshots.py
```

Usos:
1. **Avaliação de design** por agentes externos (contexto visual sem
   rodar o app);
2. **README do repositório** (preview.png é o mosaico hero).

## Arquivos

| Arquivo | Tela |
|---|---|
| `0_dashboard.png` | Dashboard (resumo, ações rápidas, log) |
| `1_dpi.png` | Controle de DPI (hero, slider, presets) |
| `2_sens.png` | Sensibilidade (hero, slider, polling rate) |
| `3_clicker.png` | Auto-Clicker (status, CPS, modo) |
| `4_macros.png` | Macros (gravação, lista) |
| `5_perfis.png` | Perfis (cards, criar/editar) |
| `6_settings.png` | Configurações (permissões HID, segurança, sistema) |
| `small_*.png` | As mesmas telas em 760×560 (prova de responsividade) |
| `preview.png` | Mosaico 2×4 de todas as telas |

Capturadas em 1050×680, tema dark, com estado fake determinístico
(G403 presente, HID disponível). Se uma tela nova for adicionada ao
app, inclua-a em `PAGES` no script.
