# Checklist de requisitos: issue #111

## Escopo funcional

- [ ] `dpi` usa `focus-3-line` U+ED4C, não fast-forward U+F177.
- [ ] `macros` usa `keyboard-line` U+EE75, não filmstrip U+ED21.
- [ ] Sidebar e headings continuam usando as mesmas chaves semânticas.
- [ ] Os dois codepoints existem no TTF subset e são suportados pelo Qt.
- [ ] Os ícones renderizam em 18 px e 24 px sem imagem vazia/tofu.
- [ ] Fonte ausente e nome desconhecido continuam retornando `None`.
- [ ] Não há emoji, fonte completa, dependência nova ou mudança em core/hardware.

## Evidência de software

- [ ] Teste dedicado falhou antes do fix por codepoints/mapeamentos ausentes.
- [ ] Teste dedicado passou depois do fix nos dois tamanhos oficiais.
- [ ] Regressões de craft/capacidades passaram.
- [ ] Smoke Xvfb passou sem hardware.
- [ ] Suíte completa offscreen passou sem falhas.
- [ ] `compileall` passou.
- [ ] `git diff --check` passou.
- [ ] Captura oficial passou e cinco PNGs afetados foram revisados.
- [ ] Revisão read-only não encontrou achados bloqueadores.
- [ ] Os três jobs reais do CI passaram.

## Rastreabilidade

| Requisito | Teste/verificação | Resultado |
|---|---|---|
| FR-001 | `test_semantic_codepoints` e captura DPI | Pendente |
| FR-002 | `test_semantic_codepoints` e captura Macros | Pendente |
| FR-003 | `test_call_sites_keep_semantic_keys` | Pendente |
| FR-004 | `QRawFont.supportsCharacter` no asset real | Pendente |
| FR-005 | `test_icon_fallback_when_font_unavailable` | Pendente |
| FR-006 | diff de dependências, grep de emoji e revisão | Pendente |
| FR-007 | `scripts/capture_screenshots.py` e diff dos cinco PNGs | Pendente |
| FR-008 | testes 18/24 px e dimensões das capturas | Pendente |

## Governança

- [ ] PR contém `Closes #111`, testes, riscos e limitações da validação.
- [ ] PR permanece aberto e não merged para decisão do mantenedor.
- [ ] Nenhuma claim de validação física do G403 foi feita.
