# Modelo de dados: cor semântica do valor CPS

Esta mudança não cria nem altera dados persistidos, entidades de domínio ou
contratos de hardware.

- O valor exibido continua sendo `AutoClickerEngine.cps`, com limites definidos
  pelo core e sem nova fonte de verdade.
- A cor é uma propriedade de apresentação do `QLabel` e usa o token existente
  `app.ui.theme.COLORS['accent_light']`.
- O token `warning` continua associado a estados reais de atenção, como a
  indisponibilidade de permissão HID em Configurações.
