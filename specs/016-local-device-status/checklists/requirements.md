# Requirements Checklist: Status local inequívoco do dispositivo

**Spec**: `../spec.md`
**Issue**: #115
**Status**: Em implementação

## Spec Quality

- [x] O problema de `Online` como status ambíguo está descrito.
- [x] A matriz cobre mouse detectado com e sem HID.
- [x] O escopo distingue conexão local de DPI e outras capacidades.
- [x] Os critérios cobrem desktop, small, hotplug e troca de página.
- [x] O escopo não inclui mudança de hardware, core ou dependências novas.

## Constitution and Architecture

- [x] Os testes usam `CapabilityModel`, `FakeState` e monitor fake.
- [x] A mudança fica na apresentação e não cria regra de domínio na UI.
- [x] O indicador não simula DPI disponível nem altera evidência do core.
- [x] O plano registra os oito princípios da constituição.
- [x] O hotplug existente continua sendo a fonte de atualização.

## Test-Driven Development

- [ ] Teste dedicado escrito antes da implementação.
- [ ] RED observado com as strings vagas do código anterior.
- [ ] GREEN observado após a mudança.

## Verification

- [ ] Matriz dedicada e regressões de hotplug/capabilities passam.
- [x] Screenshots desktop, small e preview regeneradas.
- [ ] Suíte determinística completa passa.
- [ ] Smoke Xvfb, compileall e `git diff --check` passam.
- [ ] CI real do PR está verde.
- [ ] PR aberto e não mergeado.

## Traceability

- [x] FR-001 a FR-003 têm teste para cada copy da matriz.
- [x] FR-004 tem teste com DPI indisponível e mouse/HID presentes.
- [x] FR-005 tem teste das cores associadas aos três estados.
- [x] FR-006 tem regressões de troca de página e hotplug.
- [x] FR-007 tem conferência dos caminhos de screenshots alterados.
- [x] FR-008 depende dos checks reais e da abertura do PR.
