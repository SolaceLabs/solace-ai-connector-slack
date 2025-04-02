include .env
VERSION ?= local

check-hatch:
	@which hatch > /dev/null || (echo "Hatch is not installed. Please install it with 'pip install hatch'" && exit 1)

gen-docs:
	@solace-ai-connector-gen-docs src/solace_ai_connector_slack

build: check-hatch
	@hatch build

test: check-hatch
	@hatch test
