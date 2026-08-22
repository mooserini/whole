.PHONY: build run json once check test shadow report mcp mcp-sse clean

# Xcode 27 beta owns the FoundationModels macros. Do not point this at
# /Applications/Xcode.app (that's 26.6) and do not flip xcode-select.
export DEVELOPER_DIR := /Applications/Xcode-beta.app/Contents/Developer

BIN := .build/debug/whole-clerk
FIXTURE := Fixtures/sample-trail.jsonl

build:
	swift build -c debug --product whole-clerk

run: build
	$(BIN) --trail $(FIXTURE)

json: build
	$(BIN) --trail $(FIXTURE) --json

PY := /Library/Developer/CommandLineTools/usr/bin/python3

once:
	$(PY) scripts/frontmost.py --once --store $(HOME)/.hermes/whole

check:
	mkdir -p /tmp/whole-verify
	$(PY) scripts/frontmost.py --once --store /tmp/whole-verify

test:
	PYTHONPATH=scripts $(PY) -m unittest discover -s Tests -p 'test_*.py' -v
	swift test

shadow:
	$(PY) scripts/whole_store.py import-jsonl $(HOME)/.hermes/whole/trail.jsonl

report:
	$(PY) scripts/whole_store.py report

mcp:
	PYTHONPATH=scripts $(PY) scripts/whole_mcp.py --stdio

mcp-sse:
	PYTHONPATH=scripts $(PY) scripts/whole_mcp.py --sse --host 0.0.0.0 --port 39400

clean:
	rm -rf .build
