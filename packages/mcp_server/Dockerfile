FROM python:3.13

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    echo "Asia/Shanghai" > /etc/timezone

ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8

# 安装 pip 依赖
RUN pip install uv -i https://pypi.tuna.tsinghua.edu.cn/simple/ &&  \
    uv venv

ENV PATH="/app/.venv/bin:$PATH"

RUN . .venv/bin/activate

COPY . .

RUN pip install --upgrade pip setuptools wheel -i https://pypi.tuna.tsinghua.edu.cn/simple/ && \
    # 先尝试安装可能引起问题的包
    pip install wheel setuptools_scm -i https://pypi.tuna.tsinghua.edu.cn/simple/

# 然后安装所有依赖
RUN uv sync --all-packages -i https://pypi.tuna.tsinghua.edu.cn/simple/

WORKDIR packages/MinerU-HTML/

RUN uv pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple/

WORKDIR /app

ENV PYTHONPATH=/app/packages/mcp_server/src/mcp_server:/app

ENV MODEL_CF__MODEL_PATH=/app/models/models--opendatalab--MinerU-HTML/snapshots/2498a57895e29ccf9c1d5dd60e5f68f18c1406c6

CMD ["python", "-m", "uvicorn", "packages.mcp_server.src.mcp_server.main:app", "--host", "0.0.0.0", "--port", "9506"]
