FROM sagemath/sagemath:10.9
ENV DOT_SAGE=/tmp/.sage
COPY --chown=sage:sage runner.py /opt/mathloop/runner.py
ENTRYPOINT ["sage", "-python", "/opt/mathloop/runner.py"]
