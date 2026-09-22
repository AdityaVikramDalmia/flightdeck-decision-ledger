PREFIX ?= $(HOME)/.local
.PHONY: test install

test:
	python3 -m py_compile bin/decision-ledger tests/test_decision_ledger.py
	python3 -m unittest discover -s tests -v

install:
	install -d "$(DESTDIR)$(PREFIX)/bin"
	install -m 755 bin/decision-ledger "$(DESTDIR)$(PREFIX)/bin/decision-ledger"
