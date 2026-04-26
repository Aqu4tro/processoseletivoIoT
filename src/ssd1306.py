from machine import Pin, PWM, I2C
import time
import ssd1306
import json

# -------------------------------------------------------------
# PERSISTÊNCIA (NVS - Non-Volatile Storage)
# -------------------------------------------------------------
CONFIG_FILE = "config.json"

def carregar_senha():
    try:
        with open(CONFIG_FILE, "r") as f:
            dados = json.load(f)
            return dados["senha"]
    except:
        return [1, 3, 2, 4]

def salvar_senha(nova_senha):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"senha": nova_senha}, f)

# -------------------------------------------------------------
# CONFIGURAÇÃO DE HARDWARE
# -------------------------------------------------------------
LED_GREEN  = Pin(2,  Pin.OUT)
LED_RED    = Pin(4,  Pin.OUT)
LED_YELLOW = Pin(5,  Pin.OUT)
BUZZER     = PWM(Pin(18), freq=1000, duty=0)
PIR        = Pin(15, Pin.IN)
i2c        = I2C(0, scl=Pin(22), sda=Pin(21))
oled       = ssd1306.SSD1306_I2C(128, 64, i2c)

# Adicionado o Botão 5 (Pino 26) para função Delete/Cancelar
BOTOES = {
    1: Pin(13, Pin.IN, Pin.PULL_UP),
    2: Pin(12, Pin.IN, Pin.PULL_UP),
    3: Pin(14, Pin.IN, Pin.PULL_UP),
    4: Pin(27, Pin.IN, Pin.PULL_UP),
    5: Pin(26, Pin.IN, Pin.PULL_UP) # NOVO BOTÃO
}

# -------------------------------------------------------------
# ESTADOS
# -------------------------------------------------------------
STANDBY     = "STANDBY"
IDLE        = "IDLE"
ENTERING    = "ENTERING"
GRANTED     = "GRANTED"
DENIED      = "DENIED"
ALARM       = "ALARM"
AUTH_CHANGE = "AUTH_CHANGE" # NOVO: Validação antes de mudar a senha
SET_PWD     = "SET_PWD"

# Variáveis globais
senha_atual = carregar_senha()
estado      = STANDBY
entrada     = []
tentativas  = 0
t_estado    = 0
t_interacao = 0
t_blink     = 0
blink_on    = False
t_debounce  = {1:0, 2:0, 3:0, 4:0, 5:0} # Adicionado debounce para o botão 5
t_long_press = 0

# -------------------------------------------------------------
# INTERFACE E LÓGICA
# -------------------------------------------------------------

def atualizar_oled(linha1, linha2=""):
    oled.fill(0)
    oled.text("COFRE IOT v2.0", 0, 0)
    oled.text("-" * 16, 0, 10)
    oled.text(linha1, 0, 30)
    oled.text(linha2, 0, 45)
    oled.show()

def beep(f=1000, d=50):
    BUZZER.freq(f)
    BUZZER.duty(512)
    time.sleep_ms(d)
    BUZZER.duty(0)

def mudar_estado(novo_estado):
    global estado, t_estado, blink_on, entrada
    estado = novo_estado
    t_estado = time.ticks_ms()
    LED_GREEN.off(); LED_RED.off(); LED_YELLOW.off(); BUZZER.duty(0)
    entrada = []
    
    if novo_estado == STANDBY:
        atualizar_oled("MODO ECONOMIA", "PIR ATIVO...")
    elif novo_estado == IDLE:
        atualizar_oled("SISTEMA PRONTO", "DIGITE A SENHA")
    elif novo_estado == AUTH_CHANGE:
        atualizar_oled("SENHA ANTIGA:", "PARA LIBERAR")
        LED_YELLOW.on()
        beep(1500, 100)
    elif novo_estado == SET_PWD:
        atualizar_oled("MODO CONFIG", "NOVA SENHA:")
        LED_YELLOW.on()
        beep(2000, 300)

def run():
    global estado, entrada, tentativas, t_blink, blink_on, t_interacao, senha_atual, t_long_press
    
    mudar_estado(STANDBY)
    
    while True:
        agora = time.ticks_ms()
        
        btn_pres = None
        for num, btn in BOTOES.items():
            if btn.value() == 0:
                if time.ticks_diff(agora, t_debounce[num]) > 250:
                    t_debounce[num] = agora
                    btn_pres = num
                    t_interacao = agora
                    break

        if estado == STANDBY:
            if PIR.value(): mudar_estado(IDLE)

        elif estado == IDLE:
            if BOTOES[4].value() == 0:
                if t_long_press == 0: t_long_press = agora
                elif time.ticks_diff(agora, t_long_press) > 3000:
                    t_long_press = 0
                    mudar_estado(AUTH_CHANGE) # Vai pedir senha antiga primeiro!
                    btn_pres = None
            else:
                if t_long_press > 0 and time.ticks_diff(agora, t_long_press) < 3000:
                    entrada.append(4)
                    beep()
                    mudar_estado(ENTERING)
                t_long_press = 0

            if btn_pres and btn_pres != 4 and btn_pres != 5:
                entrada.append(btn_pres)
                beep()
                mudar_estado(ENTERING)
            
            if time.ticks_diff(agora, t_interacao) > 15000: mudar_estado(STANDBY)

        elif estado == ENTERING:
            atualizar_oled("SENHA:", "*" * len(entrada))
            if btn_pres:
                if btn_pres == 5: # Lógica de Delete
                    if len(entrada) > 0:
                        entrada.pop()
                        beep(600, 50) # Bipe grave
                    else:
                        mudar_estado(IDLE) # Se apagar tudo, funciona como Cancelar
                else:
                    entrada.append(btn_pres)
                    beep()
                    if len(entrada) == 4:
                        if entrada == senha_atual:
                            tentativas = 0
                            mudar_estado(GRANTED)
                        else:
                            tentativas += 1
                            mudar_estado(ALARM if tentativas >= 3 else DENIED)

        elif estado == AUTH_CHANGE:
            atualizar_oled("SENHA ANTIGA:", "*" * len(entrada))
            if btn_pres:
                if btn_pres == 5: 
                    if len(entrada) > 0:
                        entrada.pop()
                        beep(600, 50)
                    else:
                        mudar_estado(IDLE) # Cancela e volta
                else:
                    entrada.append(btn_pres)
                    beep()
                    if len(entrada) == 4:
                        if entrada == senha_atual:
                            mudar_estado(SET_PWD) # Senha antiga correta! Pode criar nova.
                        else:
                            mudar_estado(DENIED) # Errou a senha antiga

        elif estado == SET_PWD:
            atualizar_oled("NOVA SENHA:", "*" * len(entrada))
            if btn_pres:
                if btn_pres == 5:
                    if len(entrada) > 0:
                        entrada.pop()
                        beep(600, 50)
                    else:
                        mudar_estado(IDLE) # Cancela e volta
                else:
                    entrada.append(btn_pres)
                    beep(1500, 100)
                    if len(entrada) == 4:
                        senha_atual = list(entrada)
                        salvar_senha(senha_atual)
                        atualizar_oled("SUCESSO!", "SENHA SALVA")
                        beep(2500, 500)
                        time.sleep(1)
                        mudar_estado(IDLE)

        elif estado == GRANTED:
            LED_GREEN.on()
            atualizar_oled("ACESSO OK", "BEM-VINDO")
            if time.ticks_diff(agora, t_estado) > 3000: mudar_estado(IDLE)

        elif estado == DENIED:
            LED_RED.on()
            atualizar_oled("SENHA ERRADA", "TENTE DE NOVO")
            if time.ticks_diff(agora, t_estado) > 2000: mudar_estado(IDLE)

        elif estado == ALARM:
            if time.ticks_diff(agora, t_blink) > 150:
                t_blink = agora
                blink_on = not blink_on
                LED_RED.value(blink_on)
                BUZZER.duty(512 if blink_on else 0)
                BUZZER.freq(800 if blink_on else 500)
            if time.ticks_diff(agora, t_estado) > 10000: 
                tentativas = 0
                mudar_estado(IDLE)

run()