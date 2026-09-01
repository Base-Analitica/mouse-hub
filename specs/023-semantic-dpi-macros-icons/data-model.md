# Data Model: Ícones semânticos de DPI e Macros

Esta feature não introduz entidades de domínio, persistência, configuração ou
serviços. O modelo abaixo descreve somente os elementos observáveis da UI e do
asset de fonte.

| Elemento | Tipo existente | Papel | Invariante |
|---|---|---|---|
| `dpi` | Chave semântica | Seleciona o ícone de DPI | U+ED4C em sidebar e heading |
| `macros` | Chave semântica | Seleciona o ícone de Macros | U+EE75 em sidebar e heading |
| `_CODEPOINTS` | Mapeamento Python | Liga nome semântico a glifo Remix | Não duplica codepoints nos call sites |
| `remixicon-subset.ttf` | Asset TTF | Fonte embutida dos glifos | Contém os 14 codepoints usados |
| `icon()` | API UI existente | Cria `QIcon` para 18/24 px | Retorna `None` se fonte/nome indisponível |
| `icon_label()` | API UI existente | Cria label de heading | Retorna `None` no mesmo fallback |

## Relações

- `SidebarButton` usa `icons.icon(key, color, 18)`.
- Os headings de DPI e Macros usam `ui_icons.icon_label(key, color, 24)`.
- Ambos os caminhos consultam a mesma entrada de `_CODEPOINTS`.
- O asset TTF é carregado pela função `_family()` e não por hardware, core ou
  configuração.
