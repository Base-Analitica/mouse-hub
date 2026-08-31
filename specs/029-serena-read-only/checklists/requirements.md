---
description: "Checklist de qualidade da configuração Serena read-only"
---

# Checklist: Serena read-only

## Requisitos

- [x] `.serena/project.yml` define `read_only: true` como booleano.
- [x] Os subcomandos `tools`, `overview`, `find`, `refs` e `diagnostics` permanecem no parser da ponte.
- [x] A ponte não expõe edição e o launcher continua apontando para o venv local.
- [x] O diff não toca runtime, hardware, launchers ou packaging do Mouse Hub.
- [x] O teste dedicado registra RED e GREEN.
- [x] A suíte completa, smoke, compileall, diff check e pacote passam.
- [x] O handshake real é executado ou a ausência da Serena é registrada como bloqueio.
- [x] O PR de #63 fica aberto, com CI verde e sem merge no HEAD `9600080` (workflow `33284588255`).
