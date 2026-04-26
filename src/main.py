# =============================================================
# SISTEMA DE CONTROLE DE ACESSO COM TECLADO
# Máquina de estados não-bloqueante para ESP32
# =============================================================

from machine import Pin, PWM
import time

# -------------------------------------------------------------
# CONFIGURAÇÃO DOS PINOS (ESP32 DevKit v1)
# -------------------------------------------------------------
LED_GREEN  = Pin(2,  Pin.OUT)  # Acesso liberado
LED_RED    = Pin(4,  Pin.OUT)  # Acesso negado / alarme
LED_YELLOW = Pin(5,  Pin.OUT)  # Sistema aguardando / digitando

# Inicializa o PWM no pino 18, com frequência de 1000 Hz e duty cycle 0 (desligado)

BUZZER = PWM(Pin(18), freq=1000, duty=0)

BTN1 = Pin(13, Pin.IN, Pin.PULL_UP)  # Dígito 1
BTN2 = Pin(12, Pin.IN, Pin.PULL_UP)  # Dígito 2
BTN3 = Pin(14, Pin.IN, Pin.PULL_UP)  # Dígito 3
BTN4 = Pin(27, Pin.IN, Pin.PULL_UP)  # Dígito 4

# -------------------------------------------------------------
# CONSTANTES DE CONFIGURAÇÃO
# -------------------------------------------------------------
SENHA_CORRETA  = [1, 3, 2, 4]
MAX_TENTATIVAS = 3

TIMEOUT_ENTRADA = 10_000
TEMPO_ACESSO    = 3_000
TEMPO_NEGADO    = 2_000
TEMPO_ALARME    = 10_000
DEBOUNCE_MS     = 200

# -------------------------------------------------------------
# DEFINIÇÃO DOS ESTADOS
# -------------------------------------------------------------
IDLE     = "IDLE"
ENTERING = "ENTERING"
GRANTED  = "GRANTED"
DENIED   = "DENIED"
ALARM    = "ALARM"

# -------------------------------------------------------------
# VARIÁVEIS DE CONTROLE GLOBAL
# -------------------------------------------------------------
estado     = IDLE
entrada    = []
tentativas = 0
t_estado   = 0
t_blink    = 0
blink_on   = False
t_debounce = {1: 0, 2: 0, 3: 0, 4: 0}
BOTOES     = {1: BTN1, 2: BTN2, 3: BTN3, 4: BTN4}

# -------------------------------------------------------------
# FUNÇÕES AUXILIARES
# -------------------------------------------------------------

def todos_leds_off():
    LED_GREEN.off()
    LED_RED.off()
    LED_YELLOW.off()
    BUZZER.duty(0) # <-- Altere aqui

def beep_curto():
    BUZZER.duty(512) # <-- Liga o som
    time.sleep_ms(50)
    BUZZER.duty(0)   # <-- Desliga o som

def ler_botao_pressionado():
    agora = time.ticks_ms()
    for num, btn in BOTOES.items():
        if btn.value() == 0:
            if time.ticks_diff(agora, t_debounce[num]) > DEBOUNCE_MS:
                t_debounce[num] = agora
                return num
    return None

def mudar_estado(novo_estado):
    global estado, t_estado, entrada, blink_on

    estado   = novo_estado
    t_estado = time.ticks_ms()
    blink_on = False
    todos_leds_off()

    print("[ESTADO] ->", novo_estado)

    if novo_estado == ENTERING:
        LED_YELLOW.on()
    elif novo_estado == GRANTED:
        LED_GREEN.on()
        beep_curto()
    elif novo_estado == ALARM:
        entrada = []

# -------------------------------------------------------------
# LOOP PRINCIPAL
# -------------------------------------------------------------

def run():
    global estado, entrada, tentativas, t_blink, blink_on

    print("=" * 40)
    print("  Sistema de Controle de Acesso")
    print("  Senha: [1, 3, 2, 4]")
    print("=" * 40)

    mudar_estado(IDLE)

    while True:
        agora = time.ticks_ms()
        botao = ler_botao_pressionado()

        if estado == IDLE:
            if time.ticks_diff(agora, t_blink) > 800:
                t_blink  = agora
                blink_on = not blink_on
                LED_YELLOW.value(blink_on)

            if botao:
                entrada = [botao]
                print("[ENTRADA] Botao:", botao)
                beep_curto()
                mudar_estado(ENTERING)

        elif estado == ENTERING:
            if time.ticks_diff(agora, t_estado) > TIMEOUT_ENTRADA:
                print("[TIMEOUT] Reiniciando.")
                entrada = []
                mudar_estado(IDLE)

            elif botao:
                entrada.append(botao)
                print("[ENTRADA] Sequencia:", entrada)
                beep_curto()

                if len(entrada) == len(SENHA_CORRETA):
                    if entrada == SENHA_CORRETA:
                        print("[OK] Acesso LIBERADO!")
                        tentativas = 0
                        entrada    = []
                        mudar_estado(GRANTED)
                    else:
                        tentativas += 1
                        print("[ERRO] Tentativa", tentativas, "/", MAX_TENTATIVAS)
                        entrada = []

                        if tentativas >= MAX_TENTATIVAS:
                            print("[ALARME] Bloqueado!")
                            mudar_estado(ALARM)
                        else:
                            mudar_estado(DENIED)

        elif estado == GRANTED:
            if time.ticks_diff(agora, t_estado) > TEMPO_ACESSO:
                print("[INFO] Retornando a espera.")
                mudar_estado(IDLE)

        elif estado == DENIED:
            if time.ticks_diff(agora, t_blink) > 200:
                t_blink  = agora
                blink_on = not blink_on
                LED_RED.value(blink_on)

            if time.ticks_diff(agora, t_estado) > TEMPO_NEGADO:
                mudar_estado(ENTERING)

        elif estado == ALARM:
            if time.ticks_diff(agora, t_blink) > 100:
                t_blink  = agora
                blink_on = not blink_on
                LED_RED.value(blink_on)
                
                # <-- Controle do Buzzer com PWM
                if blink_on:
                    BUZZER.duty(512)
                else:
                    BUZZER.duty(0)

            if time.ticks_diff(agora, t_estado) > TEMPO_ALARME:
                print("[INFO] Alarme desativado.")
                tentativas = 0
                BUZZER.duty(0) # <-- Garante que desliga ao sair
                mudar_estado(IDLE)

# -------------------------------------------------------------
# PONTO DE ENTRADA
# -------------------------------------------------------------
run()