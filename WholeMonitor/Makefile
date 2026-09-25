# Shipped Xcode 27 owns this build. No beta, no xcode-select flip.
export DEVELOPER_DIR := /Applications/Xcode.app/Contents/Developer

APP := Build/WholeMonitor.app
BIN := $(APP)/Contents/MacOS/WholeMonitor
SOURCES := $(wildcard Sources/*.swift)

.PHONY: build run contract-test clean

build: $(BIN)

$(BIN): $(SOURCES) Info.plist
	mkdir -p $(APP)/Contents/MacOS $(APP)/Contents/Resources
	xcrun swiftc -o $(BIN) $(SOURCES) \
		-framework SwiftUI -framework AppKit -framework Combine \
		-O -target arm64-apple-macos14.0
	cp Info.plist $(APP)/Contents/Info.plist
	codesign --force -s - $(APP)

# Proves Models.swift decodes the LIVE server before the app ships pixels.
contract-test: $(SOURCES)
	xcrun swiftc -o /tmp/whole-contract-test Sources/Models.swift Tools/contract-test.swift \
		-O -target arm64-apple-macos14.0
	/tmp/whole-contract-test

run: build
	open $(APP)

clean:
	rm -rf Build /tmp/whole-contract-test
