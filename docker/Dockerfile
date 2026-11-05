FROM ubuntu:22.04

ENV USER_NAME=ubuntu

RUN apt-get update && apt-get install -y \
    build-essential \
    clang \
    llvm \
    make \
    git \
    python3 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*
    
RUN useradd -ms /bin/sh ${USER_NAME}
RUN chown -R ${USER_NAME} /home/${USER_NAME}
USER ${USER_NAME}
    
WORKDIR /home/${USER_NAME}/rtrbench

CMD ["/bin/bash"]