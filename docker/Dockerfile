FROM ubuntu:22.04

ENV USER_NAME=ubuntu

RUN apt-get update && apt-get install -y \
    build-essential \
    clang \
    llvm \
    make \
    git \
    python3 \
    python3-pip \
    ca-certificates \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
    
RUN useradd -ms /bin/sh ${USER_NAME}
RUN chown -R ${USER_NAME} /home/${USER_NAME}
USER ${USER_NAME}
    
WORKDIR /home/${USER_NAME}/rtrbench

COPY data-gen/requirements.txt /home/${USER_NAME}/requirements.txt
RUN pip3 install --no-cache-dir -r /home/${USER_NAME}/requirements.txt

CMD ["/bin/bash"]