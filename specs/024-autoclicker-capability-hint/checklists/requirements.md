# Requirements Quality Checklist: Hint de capacidade do Auto-Clicker visível

**Purpose**: Conferir se os requisitos do issue #78 são claros, testáveis e delimitam o escopo antes da implementação.
**Created**: 2026-08-29
**Feature**: [spec.md](../spec.md)

**Review Ownership**: Checklist de qualidade dos requisitos. Os itens marcados indicam que o requisito foi revisado, não que a implementação já foi concluída.

## Clareza e rastreabilidade

- [x] CHK001 O problema identifica o widget existente (`caps_hint`) e a lacuna observável, ausência no layout.
- [x] CHK002 Cada requisito usa comportamento verificável, sem depender de interpretação visual vaga.
- [x] CHK003 Os estados disponível e indisponível têm critérios independentes.
- [x] CHK004 A causa real é vinculada explicitamente a `CapabilityState`, sem permitir mensagem genérica inventada.

## Escopo e arquitetura

- [x] CHK005 O desenho preserva `CapabilityModel`, gating, foco, hardware e persistência.
- [x] CHK006 O posicionamento do hint é definido em relação a `mc_status` e aos controles.
- [x] CHK007 O issue #83 e a remoção de jargão estão registrados como escopo separado.
- [x] CHK008 A ausência de dependências novas e de lógica de domínio está explícita.

## Verificação

- [x] CHK009 Há teste determinístico para o widget estar efetivamente no layout.
- [x] CHK010 Há teste para causa disponível/indisponível e estados dos controles.
- [x] CHK011 Os dois viewports oficiais, screenshots, smoke e pacote estão mapeados.
- [x] CHK012 A distinção entre evidência de software e validação física está registrada.

## Notes

Os itens acima são gates de qualidade da especificação. Os resultados de implementação, captura, revisão e CI serão registrados em `spec.md`, `plan.md` e `tasks.md` após a execução.
