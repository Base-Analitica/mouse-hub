---
description: "Checklist de qualidade da configuração Serena read-only"
---

# Checklist: Serena read-only

## Requisitos

- [ ] `.serena/project.yml` define `read_only: true` como booleano.
- [ ] Os subcomandos `tools`, `overview`, `find`, `refs` e `diagnostics` permanecem no parser da ponte.
- [ ] A ponte não expõe edição e o launcher continua apontando para o venv local.
- [ ] O diff não toca runtime, hardware, launchers ou packaging do Mouse Hub.
- [ ] O teste dedicado registra RED e GREEN.
- [ ] A suíte completa, smoke, compileall, diff check e pacote passam.
- [ ] O handshake real é executado ou a ausência da Serena é registrada como bloqueio.
- [ ] O PR de #63 fica aberto, com CI verde e sem merge.
