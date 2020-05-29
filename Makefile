SHELL := /usr/bin/env bash

# Get the directory containing this Makefile
# Presumes GNU make
# The patsubst strips the trailing / left by dir
PB_HOME = $(patsubst %/,%,$(dir $(realpath $(lastword $(MAKEFILE_LIST)))))

# Options most likely to be changed by user
OS_NAME ?= debian
OS_VERSION ?= 10_buster
TEMPLATE ?= base-uefi
VAR_FILE ?=

# Less common changes
BUILDER ?= vbox  # vbox or qemu
BUILD_OPTS ?=  # leave this undefined unless needed

# Locations
BUILD_DIR ?= build
PACKER_CACHE_DIR ?= packer_cache
PYTHON ?= python3
SOURCE_DIR ?= source
TEMPLATE_DIR ?= template
VENV_DIR ?= $(PB_HOME)/.venv

# Convenience variables
SOURCE_TEMPLATE_DIR = $(SOURCE_DIR)/$(OS_NAME)/$(OS_VERSION)
TARGET_TEMPLATE_DIR = $(TEMPLATE_DIR)/$(OS_NAME)/$(OS_VERSION)

SOURCE_TEMPLATE = $(SOURCE_TEMPLATE_DIR)/$(TEMPLATE).yaml
TARGET_TEMPLATE = $(TARGET_TEMPLATE_DIR)/$(TEMPLATE).json

.SUFFIXES:
.SUFFIXES: .yaml .json .iso .preseed .vagrant .ova .box

.PRECIOUS: .yaml .preseed .vagrant

.PHONY: all
all: image

# Install Python virtual environment in this directory
ACTIVATE_SCRIPT = $(VENV_DIR)/bin/activate
$(ACTIVATE_SCRIPT):
	@$(PYTHON) -m venv $(VENV_DIR)

# Install required Python packages
requirements: $(PB_HOME)/requirements.txt

$(PB_HOME)/requirements.txt: $(PB_HOME)/requirements_bare.txt $(ACTIVATE_SCRIPT)
	@source $(ACTIVATE_SCRIPT) && \
  pip install --upgrade --requirement $< && \
  pip freeze > $@

# Always regenerate the particular template being used
.PHONY: image-template
image-template $(TARGET_TEMPLATE): $(SOURCE_TEMPLATE) $(VAR_FILE) $(PB_HOME)/requirements.txt
	@source $(ACTIVATE_SCRIPT) && \
  $(PYTHON) $(PB_HOME)/generate_template.py --base_dir=$(SOURCE_DIR) --os_name=$(OS_NAME) --os_version=$(OS_VERSION) --os_template=$(TEMPLATE) --var_file=$(VAR_FILE) --verbose

# Generate all templates
.PHONY: all-templates
all-templates: $(PB_HOME)/requirements.txt
	@source $(ACTIVATE_SCRIPT) && \
  $(PYTHON) $(PB_HOME)/generate_template.py

# Build the requested image from the templates
.PHONY: image
image: $(TARGET_TEMPLATE) image-template
	CHECKPOINT_DISABLE=1 PACKER_CACHE_DIR=$(PACKER_CACHE_DIR) \
  packer build $(BUILD_OPTS) -only=$(BUILDER) -force $<

.PHONY: inspect
inspect: $(TARGET_TEMPLATE) image-template
	CHECKPOINT_DISABLE=1 PACKER_CACHE_DIR=$(PACKER_CACHE_DIR) \
  packer inspect $(BUILD_OPTS) $<

.PHONY: validate
validate: $(TARGET_TEMPLATE) image-template
	CHECKPOINT_DISABLE=1 PACKER_CACHE_DIR=$(PACKER_CACHE_DIR) \
  packer validate $(BUILD_OPTS) $<

# PACKER_CACHE_DIR=packer_cache
# PACKER_CONFIG="${HOME}/.packerconfig"
# PACKER_LOG=1
# PACKER_LOG_PATH=vbox.log
# PACKER_NO_COLOR=0
# PACKER_PLUGIN_MAX_PORT=25000
# PACKER_PLUGIN_MIN_PORT=10000
# PACKER_TMP_DIR=/tmp/packer.d
# TMPDIR=/tmp

.PHONY: clean
clean:
	@rm -rf $(TEMPLATE_DIR) $(BUILD_DIR) && \
  rm -rf Vagrantfile .vagrant

.PHONY: reallyclean
reallyclean: clean
	@rm -rf $(VENV_DIR) && \
  rm -f $(PB_HOME)/requirements.txt

.PHONY: reallyreallyclean
reallyreallyclean: reallyclean
	@rm -rf $(PACKER_CACHE_DIR)
