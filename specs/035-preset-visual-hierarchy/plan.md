# Plano de implementação: hierarquia visual dos presets

## Resumo

Criar `PresetButton`, um único `QPushButton` com dois `QLabel`s filhos: contexto secundário e valor `NNN DPI` destacado. Reutilizar a composição em `DashboardPage` e `DPIPage`, mantendo os callbacks atuais e centralizando os pares de labels com `DPI_PRESETS`.

## Estado inicial

- Base: `origin/main` em `abad8b13877ab9b870f1bbe92c12d2d21738f569`.
- Worktree: `/home/pedro/.jcode/scratch/issue94-preset-hierarchy`.
- Branch: `fix/preset-visual-hierarchy`.
- Baseline determinístico: **544 testes passaram**, exit 0.

## Arquitetura

1. Adicionar tabela privada de labels de UI para as chaves de `DPI_PRESETS`.
2. Adicionar `PresetButton(QPushButton)` em `app/mouse_hub_app.py`.
   - manter um único alvo clicável;
   - usar `TYPE_SCALE` e `COLORS` existentes;
   - tornar labels transparentes para eventos do mouse;
   - expor nome acessível e referências dos labels para testes/integradores.
3. Atualizar Dashboard para usar os quatro primeiros presets da tabela e guardar `quick_preset_buttons`.
4. Atualizar DPI para usar a mesma tabela, mantendo `preset_buttons` e `_set_preset`.
5. Não modificar core, hardware, persistência, automação ou limites.

## Estratégia de testes

- RED: teste dedicado falha antes de `PresetButton` existir.
- GREEN: teste dedicado comprova composição, acessibilidade, tipografia, valores, callbacks e containers reais.
- Regressões: `tests/test_issue3_ui_integration.py` e `tests/test_issue66_ui_craft.py`.
- Validação visual: `scripts/capture_screenshots.py` em dois diretórios temporários e comparação byte a byte.
- Empacotamento: staging `.deb` e inspeção da árvore/arquivo da aplicação.
- Entrega: suíte completa, smoke Xvfb, compileall, diff check e três jobs reais do CI.

## Riscos e mitigação

- **Overflow em 760×560:** medir Dashboard e DPI em `QScrollArea` real nos dois viewports.
- **Clique interceptado por labels:** usar `WA_TransparentForMouseEvents` e testar `clicked`.
- **Drift de valores:** gerar todos os valores a partir de `DPI_PRESETS` e testar os cinco pares.
- **Regressão de hardware:** manter lambdas e callbacks existentes; executar a integração de uma operação HID.
- **Artefatos incidentais:** comparar todos os PNGs e incluir somente Dashboard, DPI e `preview.png`.

## Sequência de validação

1. Baseline local: 544 pass.
2. Testes RED observados.
3. Implementação mínima e teste GREEN.
4. Testes focados/regressões, compileall e diff check.
5. Captura dupla determinística e revisão de bboxes.
6. Suíte completa e smoke local.
7. Build/instalação do `.deb` em ambiente limpo.
8. Commit, push, PR com `Closes #94`.
9. Confirmar exatamente os três jobs reais no SHA final.

## Constituição

- Correção de hardware: nenhum caminho HID foi alterado.
- Estado honesto: valores e callbacks existentes continuam sendo a fonte de comportamento.
- Fakes no CI: testes e captura usam fakes determinísticos.
- Menor mudança: uma composição visual compartilhada e dois pontos de montagem.
