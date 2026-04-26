# Processo Seletivo – Intensivo Maker | IoT
## Etapa Prática – Sistemas Embarcados

# 🔐 Sistema de Controle de Acesso com Teclado

## 👤 Identificação do Candidato

| Campo | Valor |
|---|---|
| **Nome completo** | _Jonathas Levi Pascoal Palmeira_ |
| **GitHub** | _https://github.com/Aqu4tro_ |

---

## 1️⃣ Visão Geral da Solução

Este projeto implementa um **sistema de controle de acesso por senha** simulado em hardware virtual (Raspberry Pi Pico via Wokwi).

O sistema aguarda que o usuário pressione uma sequência de 4 botões. Se a sequência corresponder à senha cadastrada, o acesso é liberado (LED verde). Em caso de erro, o sistema permite novas tentativas até o limite máximo, momento em que um alarme é ativado.

**Interação do usuário:** pressionar os botões na ordem correta para liberar o acesso.

---

## 2️⃣ Arquitetura do Sistema Embarcado

O sistema é baseado em uma **máquina de estados finitos (FSM)** não-bloqueante, executada em loop contínuo sem uso de `time.sleep()` bloqueante no fluxo principal.

### Diagrama de Estados

```
                    ┌─────────────────────────────────────────┐
                    │                                         │
                    ▼                                         │
              ┌───────────┐    botão pressionado    ┌─────────────┐
              │   IDLE    │ ──────────────────────► │  ENTERING   │
              │ (aguarda) │                         │  (digitando)│
              └───────────┘                         └─────────────┘
                                                         │    │
                                           senha correta │    │ senha errada
                                                         │    │ (< 3 erros)
                                                         ▼    ▼
                                                   ┌─────────┐ ┌────────┐
                                                   │ GRANTED │ │ DENIED │
                                                   │(liberado│ │(negado)│
                                                   └─────────┘ └────────┘
                                                        │           │
                                               3s depois│           │2s depois
                                                        │           │
                                                        ▼           ▼
                                                      IDLE      ENTERING
                                                                    │
                                                       senha errada │ (3º erro)
                                                                    ▼
                                                              ┌─────────┐
                                                              │  ALARM  │
                                                              │(bloqueio│
                                                              │ 10s)    │
                                                              └─────────┘
                                                                    │
                                                          10s depois │
                                                                    ▼
                                                                  IDLE
```

### Fluxo do `main.py`

1. Inicializa pinos e variáveis de controle
2. Entra no `while True` do loop principal
3. A cada iteração, lê o tempo atual (`time.ticks_ms()`) e verifica botões (com debounce)
4. Executa o bloco do estado atual: atualiza LEDs, verifica timeouts, trata entrada
5. Quando necessário, chama `mudar_estado()` para transicionar

### Temporização não-bloqueante

Toda temporização usa comparação de `ticks_ms` em vez de `sleep`, garantindo que o loop nunca fique parado esperando tempo passar.

---

## 3️⃣ Componentes Utilizados na Simulação

| Componente | Qtd | Pinos (Pico) | Função |
|---|---|---|---|
| Raspberry Pi Pico | 1 | — | Microcontrolador principal (MicroPython) |
| LED Verde | 1 | GP0 | Indica acesso liberado |
| LED Vermelho | 1 | GP1 | Indica senha errada / alarme ativo |
| LED Amarelo | 1 | GP2 | Indica estado do sistema (aguardando / digitando) |
| Buzzer | 1 | GP3 | Feedback sonoro (beep no botão, alarme contínuo) |
| Botão 1 | 1 | GP14 | Dígito 1 da senha |
| Botão 2 | 1 | GP15 | Dígito 2 da senha |
| Botão 3 | 1 | GP16 | Dígito 3 da senha |
| Botão 4 | 1 | GP17 | Dígito 4 da senha |

---

## 4️⃣ Decisões Técnicas Relevantes

### Máquina de estados (FSM)
A lógica foi organizada em 5 estados bem definidos (`IDLE`, `ENTERING`, `GRANTED`, `DENIED`, `ALARM`), com transições explícitas via `mudar_estado()`. Isso evita lógica condicional aninhada e torna o código fácil de expandir.

### Temporização não-bloqueante
Toda temporização usa `time.ticks_ms()` e `time.ticks_diff()` em vez de `time.sleep()`. O único `sleep` bloqueante é o beep de 50ms no pressionamento do botão — aceitável pois é brevíssimo e ocorre fora do fluxo principal de controle.

### Debounce por software
Cada botão possui seu próprio timestamp de debounce (`t_debounce`), evitando leituras duplicadas sem necessidade de hardware adicional.

### Senha configurável
A senha e os limites de tempo são definidos como constantes no topo do arquivo, facilitando ajustes sem modificar a lógica.

### Separação de responsabilidades
- `ler_botao_pressionado()` — leitura de hardware com debounce
- `mudar_estado()` — transições e saídas iniciais
- `todos_leds_off()` — reset de atuadores
- `run()` — loop da máquina de estados

---

## 5️⃣ Resultados Obtidos

O sistema funciona conforme esperado na simulação do Wokwi:

- **IDLE**: LED amarelo pisca lentamente (800ms), aguardando interação
- **ENTERING**: LED amarelo fixo; cada botão emite um beep e é registrado na sequência
- **Senha correta**: LED verde acende por 3 segundos e sistema retorna ao IDLE
- **Senha errada (< 3x)**: LED vermelho pisca por 2 segundos, depois permite nova tentativa
- **Alarme (3 erros)**: LED vermelho pisca rapidamente + buzzer contínuo por 10 segundos
- **Timeout**: se o usuário demorar mais de 10s para completar a senha, reinicia

Todos os requisitos funcionais foram atendidos e o pipeline do GitHub Actions executa sem erros.

---

## 6️⃣ Comentários Adicionais

### Limitações
- O sistema não possui armazenamento persistente: reinicializações resetam o contador de tentativas
- A senha é definida em texto claro no código — em produção, deveria ser armazenada de forma segura

### Melhorias com mais tempo
- Adicionar display OLED para mostrar número de dígitos digitados
- Permitir cadastro de nova senha via sequência especial
- Implementar múltiplos níveis de acesso com senhas diferentes

### Aprendizados
O principal aprendizado foi entender como estruturar firmware com máquina de estados em vez de sequências lineares com `sleep`. Essa abordagem torna o sistema muito mais responsivo e escalável.
****
