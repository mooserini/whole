.PHONY: build run json clean

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

clean:
	rm -rf .build
