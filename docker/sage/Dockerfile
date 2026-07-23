FROM sagemath/sagemath@sha256:e068670ae5863b54b2550e72437ec637b0283acb0dc712c8584c124dbf44e667
ENV DOT_SAGE=/tmp/.sage
COPY --chown=sage:sage runner.py /opt/mathloop/runner.py
ENTRYPOINT ["sage", "-python", "/opt/mathloop/runner.py"]
