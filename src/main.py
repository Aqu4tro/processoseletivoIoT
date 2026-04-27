from machine import Pin, PWM, SoftI2C
import time
import ssd1306
import json


# -------------------------------------------------------------
# PERSISTÊNCIA (NVS - Non-Volatile Storage)
# -------------------------------------------------------------
CONFIG_FILE = "config.json"

def load_password():
    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            return data["password"]
    except:
        return [1, 3, 2, 4] # Senha padrão se for a primeira vez

def save_password(new_password):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"password": new_password}, f)

# -------------------------------------------------------------
# CONFIGURAÇÃO DE HARDWARE
# -------------------------------------------------------------
LED_GREEN  = Pin(2,  Pin.OUT)
LED_RED    = Pin(4,  Pin.OUT)
LED_YELLOW = Pin(5,  Pin.OUT)
BUZZER     = PWM(Pin(18), freq=1000, duty=0)
PIR        = Pin(15, Pin.IN)

# Usando SoftI2C para estabilidade
i2c        = SoftI2C(scl=Pin(22), sda=Pin(21))
oled       = ssd1306.SSD1306_I2C(128, 64, i2c)

# Os 5 botões
BUTTONS = {
    1: Pin(13, Pin.IN, Pin.PULL_UP),
    2: Pin(12, Pin.IN, Pin.PULL_UP),
    3: Pin(14, Pin.IN, Pin.PULL_UP),
    4: Pin(27, Pin.IN, Pin.PULL_UP),
    5: Pin(26, Pin.IN, Pin.PULL_UP) # DEL / CONFIG
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
AUTH_CHANGE = "AUTH_CHANGE" # Validação da senha antiga
SET_PWD     = "SET_PWD"     # Definição da nova senha

# Variáveis globais
current_password = load_password()
state            = STANDBY
input_code       = []
attempts         = 0
t_state          = 0
t_interaction    = 0
t_blink          = 0
blink_on         = False
t_debounce       = {1:0, 2:0, 3:0, 4:0, 5:0}
t_long_press     = 0 # Temporizador para o clique longo

# -------------------------------------------------------------
# INTERFACE E LÓGICA
# -------------------------------------------------------------

def update_oled(line1, line2=""):
    oled.fill(0)
    oled.text("COFRE IOT v2.0", 0, 0)
    oled.text("-" * 16, 0, 10)
    oled.text(line1, 0, 30)
    oled.text(line2, 0, 45)
    oled.show()

def beep(f=1000, d=50):
    BUZZER.freq(f)
    BUZZER.duty(512)
    time.sleep_ms(d)
    BUZZER.duty(0)

def change_state(new_state):
    global state, t_state, blink_on, input_code
    state = new_state
    t_state = time.ticks_ms()
    LED_GREEN.off(); LED_RED.off(); LED_YELLOW.off(); BUZZER.duty(0)
    input_code = []
    
    if new_state == STANDBY:
        update_oled("MODO ECONOMIA", "PIR ATIVO...")
    elif new_state == IDLE:
        update_oled("SISTEMA PRONTO", "DIGITE A SENHA")
    elif new_state == AUTH_CHANGE:
        update_oled("SENHA ANTIGA:", "PARA LIBERAR")
        LED_YELLOW.on()
        beep(1500, 100)
    elif new_state == SET_PWD:
        update_oled("MODO CONFIG", "NOVA SENHA:")
        LED_YELLOW.on()
        beep(2000, 300)

def run():
    global state, input_code, attempts, t_blink, blink_on, t_interaction, current_password, t_long_press
    
    change_state(STANDBY)
    
    while True:
        now = time.ticks_ms()
        
        btn_pressed = None
        for num, btn in BUTTONS.items():
            if btn.value() == 0:
                if time.ticks_diff(now, t_debounce[num]) > 250:
                    t_debounce[num] = now
                    btn_pressed = num
                    t_interaction = now
                    break

        if state == STANDBY:
            if PIR.value(): change_state(IDLE)

        elif state == IDLE:
            # Lógica de segurar o botão 5 por 3 segundos
            if BUTTONS[5].value() == 0:
                if t_long_press == 0: 
                    t_long_press = now
                elif time.ticks_diff(now, t_long_press) > 3000:
                    t_long_press = 0
                    change_state(AUTH_CHANGE) # Entra no modo de trocar senha
                    btn_pressed = None # Ignora o clique
                    
                    # CORREÇÃO: Espera o usuário tirar o dedo do botão antes de continuar
                    while BUTTONS[5].value() == 0:
                        time.sleep_ms(10)
                    t_debounce[5] = time.ticks_ms() # Reseta o relógio do botão
            else:
                t_long_press = 0 # Reseta se soltar o botão antes dos 3s

            # Se apertou qualquer outro botão (1 a 4)
            if btn_pressed and btn_pressed != 5:
                input_code.append(btn_pressed)
                beep()
                change_state(ENTERING)
            
            if time.ticks_diff(now, t_interaction) > 15000: change_state(STANDBY)

        elif state == ENTERING:
            update_oled("SENHA:", "*" * len(input_code))
            if btn_pressed:
                if btn_pressed == 5:
                    if len(input_code) > 0:
                        input_code.pop()
                        beep(600, 50)
                    else:
                        change_state(IDLE)
                else:
                    input_code.append(btn_pressed)
                    beep()
                    if len(input_code) == 4:
                        if input_code == current_password:
                            beep(2000, 200)
                            attempts = 0
                            change_state(GRANTED)
                        else:
                            attempts += 1
                            change_state(ALARM if attempts >= 3 else DENIED)

        elif state == AUTH_CHANGE:
            update_oled("SENHA ANTIGA:", "*" * len(input_code))
            if btn_pressed:
                if btn_pressed == 5: 
                    if len(input_code) > 0:
                        input_code.pop()
                        beep(600, 50)
                    else:
                        change_state(IDLE) # Cancela e volta
                else:
                    input_code.append(btn_pressed)
                    beep()
                    if len(input_code) == 4:
                        if input_code == current_password:
                            change_state(SET_PWD) # Senha correta, pode criar nova
                        else:
                            change_state(DENIED) # Errou a senha antiga

        elif state == SET_PWD:
            update_oled("NOVA SENHA:", "*" * len(input_code))
            if btn_pressed:
                if btn_pressed == 5:
                    if len(input_code) > 0:
                        input_code.pop()
                        beep(600, 50)
                    else:
                        change_state(IDLE) # Cancela a troca
                else:
                    input_code.append(btn_pressed)
                    beep(1500, 100)
                    if len(input_code) == 4:
                        current_password = list(input_code)
                        save_password(current_password)
                        update_oled("SUCESSO!", "SENHA SALVA")
                        beep(2500, 500)
                        time.sleep(1)
                        change_state(IDLE)

        elif state == GRANTED:
            LED_GREEN.on()
            update_oled("ACESSO OK", "BEM-VINDO")
            if time.ticks_diff(now, t_state) > 3000: change_state(IDLE)

        elif state == DENIED:
            LED_RED.on()
            update_oled("SENHA ERRADA", "TENTE DE NOVO")
            if time.ticks_diff(now, t_state) > 2000: change_state(IDLE)

        elif state == ALARM:
            update_oled("ALARME!", "COFRE BLOQUEADO")
            if time.ticks_diff(now, t_blink) > 150:
                t_blink = now
                blink_on = not blink_on
                LED_RED.value(blink_on)
                BUZZER.duty(512 if blink_on else 0)
                BUZZER.freq(800 if blink_on else 500)
            if time.ticks_diff(now, t_state) > 10000: 
                attempts = 0
                change_state(IDLE)

run()