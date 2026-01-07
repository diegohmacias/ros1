FROM ros:noetic-ros-base

# Install dependencies for GUI and Python tools
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-tk \
    python3-pyqt5 \
    x11-apps \
    ros-noetic-plotjuggler-ros \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir pandas

# Set up colored terminal
ENV TERM=xterm-256color
ENV force_color_prompt=yes

# Add color to bash prompt and aliases
RUN echo 'PS1="\[\033[1;32m\]\u@ros1\[\033[0m\]:\[\033[1;34m\]\w\[\033[0m\]\$ "' >> /etc/bash.bashrc && \
    echo 'alias ls="ls --color=auto"' >> /etc/bash.bashrc && \
    echo 'alias ll="ls -la --color=auto"' >> /etc/bash.bashrc && \
    echo 'alias grep="grep --color=auto"' >> /etc/bash.bashrc && \
    echo 'alias plotjuggler="rosrun plotjuggler plotjuggler"' >> /etc/bash.bashrc

CMD ["bash"]