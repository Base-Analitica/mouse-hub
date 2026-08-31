# Arquitetura e direção de produto — Mouse Hub

## Missão

O Mouse Hub é um **motor local de controle e automação de entrada humana** para Linux, com mouse e teclado como superfícies de input e com controle de hardware baseado em capacidades explícitas.

O Logitech G403 HERO permanece como o primeiro caminho concreto de hardware e como o dispositivo atualmente suportado pelo controle HID++, mas **não define mais o limite conceitual do produto**.

A direção do produto é:

> Local input control and automation engine for mouse and keyboard, with capability-aware hardware control.

## Estado atual x arquitetura alvo

A documentação deve distinguir o que já existe do que é direção arquitetural.

### Implementado atualmente

- detecção e controle suportado do Logitech G403 HERO;
- DPI físico via HID++ e sensibilidade do sistema como capacidades separadas;
- perfis e presets;
- auto-clicker;
- persistência e reprodução de macros;
- captura explícita de eventos via XRecord;
- emissão de input via XTest;
- UI desktop PyQt5.

### Direção arquitetural

O core deve evoluir para um engine de entrada genérico o suficiente para representar mouse, teclado, timing e composição de ações sem duplicar mecanismos por feature.

## Camadas de responsabilidade

```text
Mouse Hub
│
├── Input Engine
│   ├── Mouse
│   ├── Keyboard
│   ├── Timing
│   ├── Sequences
│   └── Scheduler
│
├── Automation
│   ├── Auto-clicker
│   ├── Macros
│   ├── Hotkeys
│   └── Profiles
│
├── Device Control
│   └── capability-aware adapters
│       └── Logitech G403 HERO (primeiro adapter)
│
└── UI
```

### Input Engine

Responsável por representar e executar ações de entrada de forma tipada e previsível. A arquitetura deve convergir para primitivas equivalentes a:

- `mouse.move`;
- `mouse.button.down` / `mouse.button.up`;
- `mouse.scroll`;
- `keyboard.key.down` / `keyboard.key.up`;
- `wait`;
- `sequence`;
- `repeat`;
- agendamento controlado quando necessário.

A API exata pode mudar durante a implementação. O importante é preservar a separação entre **primitivas de entrada** e features de alto nível.

### Automation

Auto-clicker, macros, hotkeys e perfis são consumidores/composições do Input Engine. Eles não devem desenvolver emissores paralelos de mouse ou teclado se o engine já puder representar a operação.

O auto-clicker, por exemplo, é conceitualmente uma sequência repetida de botão + timing; não precisa constituir um segundo motor de execução.

### Device Control

Configuração de hardware é um domínio separado da emissão genérica de input.

Novos dispositivos só entram por adapters/capabilities explícitos. A existência de suporte a teclado no Input Engine **não significa** que o Mouse Hub passa automaticamente a configurar firmware, RGB, polling rate ou recursos proprietários de qualquer teclado conectado.

O hardware real continua sendo autoridade. Uma capability só pode aparecer como disponível quando existe evidência suficiente de suporte; falha de hardware não pode ser convertida em falso sucesso de UI ou persistência.

## Fronteiras do produto

### O Mouse Hub deve fazer

- emitir ações locais de mouse e teclado;
- compor ações em sequências/macros;
- controlar timing e repetição;
- oferecer auto-clicker e hotkeys como interfaces convenientes sobre o engine;
- gravar eventos somente em modos explícitos de captura;
- controlar capacidades de hardware para dispositivos com adapter implementado;
- funcionar de forma independente do restante da Anakyklos.

### O Mouse Hub não deve virar

- uma suíte universal de configuração de qualquer periférico;
- um sistema de RPA ou automação semântica de aplicações;
- um agente que interpreta telas e decide sozinho o que clicar;
- um controlador de janelas/aplicações de propósito geral;
- um keylogger global contínuo;
- um ponto de captura silenciosa de tudo o que o usuário digita.

A fronteira central é:

> **Mouse Hub executa ações de entrada; ele não decide semanticamente como operar aplicações.**

Um sistema externo pode solicitar uma sequência autorizada de input. A interpretação de intenções como "abra o navegador e faça X" pertence a uma camada acima, não ao Mouse Hub.

## Segurança de teclado

Suporte a teclado aumenta a sensibilidade do domínio. Portanto:

1. captura global contínua não é parte da arquitetura;
2. gravação deve exigir modo explícito e observável;
3. lifecycle de captura deve ter início, cancelamento e término claros;
4. dados capturados devem ser limitados ao necessário para a feature ativa;
5. emissão de teclado e captura de teclado são capabilities distintas;
6. ausência ou falha de uma capability deve degradar somente a função afetada.

## Invariantes

- UI não é fonte de verdade sobre hardware.
- DPI físico e sensibilidade do sistema permanecem conceitos separados.
- Hardware não confirmado não produz estado fictício de sucesso.
- Features de automação reutilizam primitivas do Input Engine em vez de duplicar emissores.
- Backends de plataforma permanecem substituíveis/fakeáveis para testes determinísticos.
- Nenhum busy-wait ou polling desnecessário deve ser introduzido para suportar o engine.
- O produto deve continuar leve e útil isoladamente, sem depender de Katherine ou Ouroboros.

## Estratégia de evolução

A nova direção é uma **evolução**, não uma reescrita imediata. Mudanças futuras devem extrair abstrações a partir de necessidades reais do código existente, preservando comportamento e testes. Não criar antecipadamente uma hierarquia grande de dispositivos ou um framework universal de input sem um caso concreto que a justifique.
