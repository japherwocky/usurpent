.PHONY: init demo clean dev test

init:
	python3 -m venv ./env
	./env/bin/pip install -r requirements.txt

demo:
	./env/bin/python usurpent.py

dev:
	./env/bin/python usurpent.py --debug

clean:
	rm -rf ./env

test:
	./env/bin/python -m tornado.testing tests