"""Persistência real do DPI efetivamente aplicado.

Composição testável entre o `MouseController` (que conhece o ACK
físico) e a `ConfigStore` (que conhece o arquivo XDG):

* o persister padrão (`DpiConfigPersister`) salva o DPI confirmado
  EM config.json SOMENTE depois de o hardware responder com ACK
  correlacionado (quem chama é o controller, no caminho de sucesso);
* persiste o valor EFFECTIVE (normalizado), nunca o solicitado;
* timeout ou rejeição do dispositivo NUNCA invocam o persister —
  o applied_dpi persistido permanece intocado;
* falha de persistência não apaga a configuração: o persister lê a
  config atual, altera apenas `applied_dpi` e reescreve com a mesma
  escrita atômica de `save_config`;
* `persist_applied_dpi(effective)` devolve `bool` — True persistido,
  False falhou (hardware confirmou, persistência não — os dois
  estados ficam explícitos para quem usa).

Não acopla UI dentro do controller: o controller recebe qualquer
`persister` com essa assinatura; o padrão aqui é injetável.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from mouse_hub.core import config as config_module


def persist_applied_dpi(
    effective: int,
    paths: Optional[config_module.ConfigPaths] = None,
) -> bool:
    """Persiste o DPI confirmado na configuração XDG.

    Levanta exceção se a persistência falhar (quem chama decide o
    tratamento — o controller converte em estado explícito)."""
    paths = paths or config_module.ConfigPaths.xdg()
    # Carrega SEM strict: qualquer problema no arquivo vira ConfigError
    # aqui e não sobrescreve nada; a config persistida é SEMPRE a que
    # o usuário tem (validada) + applied_dpi atualizado.
    outcome = config_module.load_config_outcome(paths, strict=False)
    data: Dict[str, Any] = dict(outcome.config)
    data["applied_dpi"] = effective
    config_module.save_config(data, paths)
    return True
