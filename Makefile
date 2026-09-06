# Windows venvs put binaries in Scripts/, Unix in bin/.
ifeq ($(OS),Windows_NT)
    PY := ./env/Scripts/python.exe
    PIP := ./env/Scripts/pip.exe
    PYTHON := python
else
    PY := ./env/bin/python
    PIP := ./env/bin/pip
    PYTHON := python3
endif

.PHONY: init demo dev clean test

init:
	$(PYTHON) -m venv ./env
	$(PIP) install -r requirements.txt

demo:
	$(PY) usurpent.py

dev:
	$(PY) usurpent.py --debug

# shutil so clean works from cmd, PowerShell or bash alike.
clean:
	$(PYTHON) -c "import shutil; shutil.rmtree('env', ignore_errors=True)"

test:
	$(PY) usurpent.py --runtests=true
