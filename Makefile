.PHONY: compile-deps install-deps clean lint

WITH_ENV = env `cat .env 2>/dev/null | xargs`

compile-deps:
	@[ -n "$(VIRTUAL_ENV)" ] || (echo 'out of virtualenv'; exit 1)
	@echo "Compiling dependencies..."
	@$(WITH_ENV) pip install -U --index-url=https://pypi.mirrors.ustc.edu.cn/simple pip setuptools wheel
	@$(WITH_ENV) pip install -U --index-url=https://pypi.mirrors.ustc.edu.cn/simple pip-tools
	@$(WITH_ENV) pip-compile -U --output-file requirements-dev.txt requires/*.in

install-deps:
	@[ -n "$(VIRTUAL_ENV)" ] || (echo 'out of virtualenv'; exit 1)
	@echo "Installing dependencies..."
	@$(WITH_ENV) pip install -U --index-url=https://pypi.mirrors.ustc.edu.cn/simple pip setuptools wheel
	@$(WITH_ENV) pip install -U --index-url=https://pypi.mirrors.ustc.edu.cn/simple pip-tools
	@$(WITH_ENV) pip-sync requirements-dev.txt

clean:
	@rm -rf dist
	@find . -name '*.pyc' -or -name '*.pyo' -or -name '__pycache__' -type f -delete
	@find . -type d -empty -delete

isort:
	@[ -n "$(VIRTUAL_ENV)" ] || (echo 'out of virtualenv'; exit 1)
	@$(WITH_ENV) isort muso

lint:
	@[ -n "$(VIRTUAL_ENV)" ] || (echo 'out of virtualenv'; exit 1)
	@$(WITH_ENV) flake8

dist: clean
	@[ -n "$(VIRTUAL_ENV)" ] || (echo 'out of virtualenv'; exit 1)
	@$(WITH_ENV) python -m build
