"""Persistência real do DPI efetivamente aplicado.

Composição testável entre o `MouseController` (que conhece o ACK
físico) e a `ConfigStore` (que conhece o arquivo XDG):

* o persister padrão (`DpiConfigPersister`) salva o DPI confirmado
  EM config.json SOMENTE depois de o hardware responder com ACK
  correlacionado (quem chama é o controller, no caminho de sucesso);
* persiste o valor EFFECTIVE (normalizado), nunca o solicitado;
* timeout ou rejeição do dispositivo NUNCA invocam o persister —
  o applied_dpi persistido permanece intocado;
* **invariável fail-closed**: o persister só escreve quando os dados
  carregados são CONFIRMADOS:

  - `LoadKind.FILE`            → OK: arquivo válido lido;
  - `LoadKind.DEFAULT` com arquivo **realmente ausente**
    (primeira execução legítima) → OK: cria a config;
  - `LoadKind.CORRUPTED` / `LoadKind.IO_ERROR` → NUNCA escreve
    (dados não confirmados; escrever seria sobrescrever o real com
    default);
  - `LoadKind.DEFAULT` com arquivo **existente** → NUNCA escreve
    (o arquivo existe mas não é confiável — tratar como corrupção);

* os bytes do arquivo original permanecem idênticos em qualquer
  caminho de bloqueio;
* `persist_applied_dpi(effective)` devolve `bool` — True persistido,
  False bloqueado ou falhou (hardware confirmou, persistência não —
  os dois estados ficam explícitos para quem usa).

Não acopla UI dentro do controller: o controller recebe qualquer
`persister` com essa assinatura; `NeverDpiPersister` é o no-op
usável em testes e no caminho sem configuração.
"""

from __future__ import annotations

from typing import Optional

from mouse_hub.core import config as config_module
from mouse_hub.core.config import LoadKind


class NeverDpiPersister:
    """Persister que nunca persiste — usado em testes e em ambientes
    onde o controller não deve tocar em disco."""

    def persist_applied_dpi(self, effective: int) -> bool:
        return False


class DpiConfigPersister:
    """Persiste applied_dpi na config XDG, guardado pela invariável
    fail-closed descrita no módulo."""

    def __init__(self, paths: Optional[config_module.ConfigPaths] = None):
        self._paths = paths or config_module.ConfigPaths.xdg()

    def persist_applied_dpi(self, effective: int) -> bool:
        paths = self._paths
        outcome = config_module.load_config_outcome(paths, strict=False)
        if outcome.kind == LoadKind.FILE:
            data = dict(outcome.config)
            data["applied_dpi"] = effective
            config_module.save_config(data, paths)
            return True
        if (
            outcome.kind == LoadKind.DEFAULT
            and not paths.config_file.exists()
        ):
            # Primeira execução legítima: criar a config com o estado
            # confirmado (defaults preservados para todo o resto).
            data = dict(outcome.config)
            data["applied_dpi"] = effective
            config_module.save_config(data, paths)
            return True
        # CORRUPTED / IO_ERROR / DEFAULT + arquivo existente:
        # dados não confirmados — escrever seria destruir o real.
        return False
