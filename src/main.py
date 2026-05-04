import time
import sys
import json
import network
import ntptime
import urequests
from machine import Pin, PWM, SoftI2C
import ssd1306

# Feedback imediato para o CI
print("Teste")
time.sleep(1)

# --- Configurações do Telegram (substitua pelos seus dados) ---
BOT_TOKEN = "Seu Bot Token aqui"
CHAT_ID = "Seu Chat ID aqui"


def send_telegram(message):
    try:
        # Codifica a mensagem para formato de URL (espacos viram %20)
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?chat_id={CHAT_ID}&text={message}"
        res = urequests.get(url)
        res.close()  # Importante fechar a conexão para liberar memória
        print(f"Telegram enviado: {message}")
    except Exception as e:
        print(f"Erro ao enviar Telegram: {e}")


# -------------------------------------------------------------
# Internet e relógio (NTP)
# -------------------------------------------------------------
def connect_wifi():
    print("Conectando ao Wi-Fi Wokwi-GUEST...")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect('Wokwi-GUEST', '')
    while not wlan.isconnected():
        print(".", end="")
        time.sleep(0.5)
    print(f"\nConectado! IP: {wlan.ifconfig()[0]}")


def sync_time():
    try:
        ntptime.host = "pool.ntp.org"
        ntptime.settime()
        print("Horário sincronizado com sucesso!")
    except:
        print("Erro ao sincronizar horário.")


def get_formatted_time():
    # O fuso do Brasil é UTC-3 (-10800 segundos)
    t = time.localtime(time.time() - 10800)
    return "{:02d}:{:02d}:{:02d}".format(t[3], t[4], t[5])


def get_timestamp():
    """Retorna data e hora formatadas para o Brasil (UTC-3)"""
    t = time.localtime(time.time() - 10800)
    # Formato: DD/MM/AAAA HH:MM:SS
    return "{:02d}/{:02d}/{:04d} {:02d}:{:02d}:{:02d}".format(t[2], t[1], t[0], t[3], t[4], t[5])


# -------------------------------------------------------------
# Persistência (NVS - Non-Volatile Storage)
# -------------------------------------------------------------
CONFIG_FILE = "config.json"


def load_config():
    """Carrega as configurações salvas ou define o padrão de fábrica."""
    default_config = {
        "password": ['1', '3', '2', '4'],
        "attempts": 0,
        "is_locked": False
    }
    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            # Verifica se as chaves existem, se não, usa as do default
            for key in default_config:
                if key not in data:
                    data[key] = default_config[key]
            return data
    except:
        return default_config


def save_config(password, attempts, is_locked):
    """Salva todo o estado atual no armazenamento interno."""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump({
                "password": password,
                "attempts": attempts,
                "is_locked": is_locked
            }, f)
    except Exception as e:
        print(f"Erro ao salvar config: {e}")


# -------------------------------------------------------------
# Hardware: LEDs, Buzzer, PIR, OLED e Teclado Matricial
# -------------------------------------------------------------
try:
    LED_GREEN = Pin(2,  Pin.OUT)
    LED_RED = Pin(4,  Pin.OUT)
    LED_YELLOW = Pin(5,  Pin.OUT)
    BUZZER = PWM(Pin(18), freq=1000, duty=0)
    PIR = Pin(15, Pin.IN)

    i2c = SoftI2C(scl=Pin(22), sda=Pin(21))
    oled = ssd1306.SSD1306_I2C(128, 64, i2c)
except Exception as e:
    print("\n--- ERRO DE HARDWARE DETECTADO ---")
    sys.print_exception(e)

    class FakeOled:
        def fill(self, x): pass
        def text(self, t, x, y): pass
        def show(self): pass
    oled = FakeOled()

# Configuração do Teclado Matricial
ROWS = [Pin(p, Pin.OUT) for p in [13, 12, 14, 27]]
COLS = [Pin(p, Pin.IN, Pin.PULL_UP) for p in [26, 25, 33, 32]]

KEYS = [
    ['1', '2', '3', 'A'],
    ['4', '5', '6', 'B'],
    ['7', '8', '9', 'C'],
    ['*', '0', '#', 'D']
]


def read_keypad():
    """Varre a matriz e retorna a tecla pressionada ou None"""
    for i, row in enumerate(ROWS):
        row.value(0)  # Ativa a linha (LOW)
        for j, col in enumerate(COLS):
            if col.value() == 0:  # Verifica se a coluna foi puxada para LOW
                row.value(1)  # Desativa a linha antes de retornar
                return KEYS[i][j]
        row.value(1)  # Desativa a linha
    return None


# -------------------------------------------------------------
# Estados do sistema e lógica principal
# -------------------------------------------------------------
STANDBY, IDLE, ENTERING = "STANDBY", "IDLE", "ENTERING"
GRANTED, DENIED, ALARM = "GRANTED", "DENIED", "ALARM"
AUTH_CHANGE, SET_PWD = "AUTH_CHANGE", "SET_PWD"

# Carrega as configs na inicialização do sistema
config = load_config()
current_password = config["password"]
attempts = config["attempts"]
is_locked = config["is_locked"]

# Se o sistema estava bloqueado mantem, liga já no alarme
state = ALARM if is_locked else STANDBY

input_code = []
t_state, t_interaction, t_blink = 0, 0, 0
blink_on = False
last_key = None
t_last_press = 0
t_long_press = 0
last_clock_update = 0


def update_oled(line1, line2=""):
    oled.fill(0)
    oled.text("COFRE IOT v2.0", 0, 0)
    oled.text("-" * 16, 0, 10)
    oled.text(line1, 0, 30)
    oled.text(line2, 0, 45)
    oled.show()


def beep(f=1000, d=50):
    try:
        BUZZER.freq(f)
        BUZZER.duty(512)
        time.sleep_ms(d)
        BUZZER.duty(0)
    except:
        pass


def change_state(new_state):
    global state, t_state, input_code, attempts
    state = new_state

    # Apaga tudo no início da troca de estado
    LED_GREEN.off()
    LED_RED.off()
    LED_YELLOW.off()
    BUZZER.duty(0)
    input_code = []

    # Inicia o cronômetro
    t_state = time.ticks_ms()

    if new_state == STANDBY:
        update_oled("MODO ECONOMIA", get_formatted_time())

    elif new_state == IDLE:
        update_oled("SISTEMA PRONTO", "DIGITE A SENHA")

    elif new_state == AUTH_CHANGE:
        update_oled("SENHA ANTIGA:", "PARA LIBERAR")
        LED_YELLOW.on()

    elif new_state == SET_PWD:
        update_oled("MODO CONFIG", "NOVA SENHA:")
        LED_YELLOW.on()

    elif new_state == GRANTED:
        update_oled("ACESSO OK", "BEM-VINDO")
        LED_GREEN.on()
        attempts = 0
        save_config(current_password, 0, False)
        send_telegram(f"Cofre Aberto em: {get_timestamp()}")
        t_state = time.ticks_ms()
        
    elif new_state == DENIED:
        update_oled("SENHA ERRADA", "TENTE DE NOVO")
        LED_RED.on()

    elif new_state == ALARM:
        update_oled("ALARME!", "COFRE BLOQUEADO")
        LED_RED.on()
        save_config(current_password, attempts, True)

        send_telegram(f"ALERTA: Tentativa de invasão em: {get_timestamp()}")

        # Reinicia o cronômetro após o bloqueio da internet
        t_state = time.ticks_ms()


def run():
    global state, input_code, attempts, t_blink, blink_on, t_interaction
    global current_password, t_long_press, last_clock_update, last_key, t_last_press

    # Inicia a conexão de internet e pega a hora antes do loop
    connect_wifi()
    sync_time()

    change_state(STANDBY)

    while True:
        try:
            now = time.ticks_ms()

            # --- Leitura do Teclado ---
            current_key = read_keypad()
            btn_pressed = None

            if current_key is not None:
                if current_key != last_key:  # Nova tecla pressionada
                    if time.ticks_diff(now, t_last_press) > 150:  # Debounce
                        btn_pressed = current_key
                        last_key = current_key
                        t_last_press = now
                        t_interaction = now
            else:
                last_key = None  # Tecla foi solta

            # --- Lógica de Estados ---
            if state == STANDBY:
                if time.ticks_diff(now, last_clock_update) > 1000:
                    update_oled("MODO ECONOMIA",
                                f"Hora: {get_formatted_time()}")
                    last_clock_update = now
                if PIR.value() or btn_pressed:
                    change_state(IDLE)

            elif state == IDLE:
                # Detecção de Long Press na tecla '#' para trocar a senha
                if current_key == '#':
                    if t_long_press == 0:
                        t_long_press = now
                    elif time.ticks_diff(now, t_long_press) > 3000:
                        t_long_press = 0
                        change_state(AUTH_CHANGE)
                        while read_keypad() == '#':
                            time.sleep_ms(10)  # Espera soltar o botão
                else:
                    t_long_press = 0

                if btn_pressed and btn_pressed not in ['#', '*']:
                    input_code.append(btn_pressed)
                    beep()
                    change_state(ENTERING)
                if time.ticks_diff(now, t_interaction) > 15000:
                    change_state(STANDBY)

            elif state == ENTERING:
                update_oled("SENHA:", "*" * len(input_code))
                if btn_pressed:
                    if btn_pressed == '*':  # Tecla de Apagar (DEL)
                        if len(input_code) > 0:
                            input_code.pop()
                            beep(600, 50)
                        else:
                            change_state(IDLE)
                    elif btn_pressed == '#':  # Cancela tudo e volta
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
                                change_state(
                                    ALARM if attempts >= 3 else DENIED)

            elif state == AUTH_CHANGE:
                update_oled("SENHA ANTIGA:", "*" * len(input_code))
                if btn_pressed:
                    if btn_pressed == '*':
                        if len(input_code) > 0:
                            input_code.pop()
                        else:
                            change_state(IDLE)
                    elif btn_pressed == '#':
                        change_state(IDLE)
                    else:
                        input_code.append(btn_pressed)
                        if len(input_code) == 4:
                            if input_code == current_password:
                                change_state(SET_PWD)
                            else:
                                change_state(DENIED)

            elif state == SET_PWD:
                update_oled("NOVA SENHA:", "*" * len(input_code))
                if btn_pressed:
                    if btn_pressed == '#' or btn_pressed == '*':
                        change_state(IDLE)
                    else:
                        input_code.append(btn_pressed)
                        if len(input_code) == 4:
                            current_password = list(input_code)

                            # Salva usando a função nova
                            save_config(current_password, 0, False)

                            update_oled("SUCESSO!", "SENHA SALVA")

                            # Envia a notificação para o telegram alvo
                            send_telegram(
                                f"Senha alterada com sucesso em: {get_timestamp()}")

                            time.sleep(1)
                            change_state(IDLE)

            elif state == GRANTED:
            
                if time.ticks_diff(now, t_state) > 3000:
                    change_state(IDLE)

            elif state == DENIED:
                
                if time.ticks_diff(now, t_state) > 2000:
                    change_state(IDLE)

            elif state == ALARM:
                # O Alarme continua igual, ele precisa piscar no loop
                if time.ticks_diff(now, t_blink) > 150:
                    t_blink = now
                    blink_on = not blink_on
                    LED_RED.value(blink_on)

        except Exception as e:
            print(f"Erro no loop principal: {e}")
            time.sleep(1)


if __name__ == "__main__":
    run()
