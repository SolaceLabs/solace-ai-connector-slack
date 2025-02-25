include .env
VERSION ?= local

gen-docs:
	@solace-ai-connector-gen-docs src/solace_ai_connector_slack

build: gen-docs
	@python3 -m build

test:
	@pytest
