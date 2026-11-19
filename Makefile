ABBS_ARGS = $(if $(ABBS_TREE),--abbs-tree "$(ABBS_TREE)")

.PHONY: all build check check-examples test

all: check test build

check:
	PYTHONDONTWRITEBYTECODE=1 python3 tools/asmr.py check $(ABBS_ARGS)

check-examples:
	PYTHONDONTWRITEBYTECODE=1 python3 tools/asmr.py check --root examples

test:
	PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v

build:
	PYTHONDONTWRITEBYTECODE=1 python3 tools/asmr.py build $(ABBS_ARGS)

