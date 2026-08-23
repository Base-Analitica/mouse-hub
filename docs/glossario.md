# Glossário de termos do projeto

Glossário dos termos técnicos usados no mouse-hub (controlador do Logitech G403 HERO).

DPI: Medida de sensibilidade óptica do sensor do mouse — quantos pixels o cursor se move por polegada física deslocada. No G403 HERO, o valor de DPI é configurado no hardware via protocolo HID++ e respeita os limites definidos em `mouse_hub/core/constants.py` (`DPI_MIN`, `DPI_MAX`, `DPI_STEP`).

Polling rate: Frequência com que o mouse reporta sua posição ao computador, medida em Hz (informes por segundo). Um polling rate maior reduz a latência entre o movimento físico e o cursor na tela; os valores suportados pelo projeto estão centralizados em `POLLING_RATES`.

Macro: Sequência pré-gravada de eventos de entrada (cliques, pressionamentos de tecla, intervalos) executada automaticamente por um único gatilho. No mouse-hub, macros são criadas e gerenciadas pela UI nativa PyQt5 para automatizar ações repetitivas.
