
FROM espressif/idf:v5.2.2


ENV IDF_PATH="/opt/esp/idf/"


WORKDIR /

COPY src/main.py /main.py
COPY src/ssd1306.py /ssd1306.py


RUN git clone https://github.com/earlephilhower/mklittlefs.git && \
    cd mklittlefs && \
    git submodule update --init && \
    make dist


RUN mkdir -p /fs_dir && \
    cp /main.py /fs_dir/main.py && \
    cp /ssd1306.py /fs_dir/ssd1306.py && \
    ./mklittlefs/mklittlefs -c /fs_dir -b 4096 -p 256 -s 0x200000 /fs.bin


CMD ["ls", "-l", "/fs.bin"]