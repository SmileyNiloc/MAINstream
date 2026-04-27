# Use the official Microsoft Python Dev Container image
FROM mcr.microsoft.com/devcontainers/python:3.12-bookworm

# Install Tkinter system dependencies
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends python3-tk tk-dev
    
# Switch from root to the default 'vscode' user to install uv safely
USER vscode

# Install uv using the official standalone installer
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Add uv to the PATH for the vscode user
ENV PATH="/home/vscode/.local/bin:/home/vscode/.cargo/bin:${PATH}"