# Requirements Checklist: Cópia explícita para estado desconhecido

**Spec**: `../spec.md`
**Issue**: #110
**Status**: Concluído, CI verde

## Spec Quality

- [x] O problema do traço colorido e seu impacto na interpretação do estado
      estão descritos.
- [x] O resultado esperado é observável por meio de texto e estilo da UI.
- [x] Os cenários cobrem dashboard, DPI, sensibilidade e layout small.
- [x] Os edge cases distinguem dispositivo ausente, falha, prévia e input.
- [x] O escopo exclui mudanças de hardware, domínio e layout não necessárias.
- [x] Não há requisito que dependa de medição física para passar no CI.

## Constitution and Architecture

- [x] A UI representa `MouseCoreState` e não inventa valor aplicado.
- [x] O teste usa fakes, sem depender do G403 HERO ou de X11 real.
- [x] A copy voltada ao usuário está em pt-BR e não expõe jargão interno.
- [x] O placeholder do input editável permanece separado do estado aplicado.
- [x] A mudança não adiciona dependência nem regra de domínio em `app/`.
- [x] A tabela de conformidade dos oito princípios está no plano.

## Verification

- [x] Existe teste dedicado para o contrato do issue.
- [x] A execução RED foi observada antes da implementação.
- [x] A execução GREEN do teste dedicado e da integração foi observada.
- [x] Screenshots desktop, small e preview foram regeneradas.
- [x] A suíte determinística completa local foi executada com exit code 0.
- [x] Smoke Xvfb, compileall e `git diff --check` estão registrados após o
      último ajuste.
- [x] Os três checks reais do PR estão verdes no workflow `33252603466`.
- [x] O PR foi aberto e permanece sem merge ([#133](https://github.com/Base-Analitica/mouse-hub/pull/133)).

## Traceability

- [x] FR-001 a FR-008 têm implementação e teste local correspondente.
- [x] FR-009 tem os artefatos de screenshot no diff.
- [x] FR-010 tem evidência remota de CI e PR.
