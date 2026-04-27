# Use a imagem oficial do ESP-IDF
FROM espressif/idf:v5.2.2

# Configura o caminho do ESP-IDF
ENV IDF_PATH="/opt/esp/idf/"

# Garante que estamos trabalhando na raiz do container
WORKDIR /

# 1. Copia os arquivos do seu repositório para a raiz do container
COPY src/main.py /main.py
COPY src/ssd1306.py /ssd1306.py

# 2. Clona e compila o mklittlefs
RUN git clone https://github.com/earlephilhower/mklittlefs.git && \
    cd mklittlefs && \
    git submodule update --init && \
    make dist

# 3. Cria a pasta final, move os arquivos copiados e gera o fs.bin
RUN mkdir -p /pasta_fs && \
    cp /main.py /pasta_fs/main.py && \
    cp /ssd1306.py /pasta_fs/ssd1306.py && \
    ./mklittlefs/mklittlefs -c /pasta_fs -b 4096 -p 256 -s 0x200000 /fs.bin

# 4. Comando final para o CI copiar o arquivo e encerrar
CMD ["ls", "-l", "/fs.bin"]