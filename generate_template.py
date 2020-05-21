#!/usr/bin/env python

import json
import click

from os import getcwd, listdir, makedirs, path, sep
from codecs import open as copen
from glob import glob
from collections.abc import Mapping
from ruamel.yaml import YAML
from jinja2 import Environment, FileSystemLoader, TemplateNotFound


YAML_EXTENSIONS = ('yml', 'yaml')

# File name endings identifying backup files from editing
IGNORED_SUFFIXES = ('~', '#')

# Packer is more picky about what keys it allows in templates starting in
# 1.4.0.  See https://github.com/hashicorp/packer/issues/7544 for details.  The
# list found at http://packer.io/docs/templates/index.html should be consulted
# from time-to-time

PACKER_TEMPLATE_KEYS = ('builders', 'description', 'min_packer_version',
                        'post-processors', 'provisioners', 'variables')

# Finding this in the 'variables' section of the YAML file tells us
# which templates to process.

PB_TEMPLATES_KEY = 'pb_templates'
PB_SOURCE_DIR = 'pb_source_dir'
PB_TEMPLATE_DIR = 'pb_template_dir'


def get_os_names(base_dir):
    '''
    '''

    os_names = []
    os_names.extend(listdir(base_dir))
    return sorted(os_names)


def get_os_versions(base_dir, os_name):
    '''
    '''

    os_versions = path.join(base_dir, os_name)
    return listdir(os_versions)


def get_os_templates(base_dir, os_name, os_version):
    '''
    '''

    os_templates = path.join(base_dir, os_name, os_version)
    return [path.splitext(file)[0] for file in listdir(os_templates)
            if file.endswith(YAML_EXTENSIONS)]


def check_os_version(ctx, param, value):
    '''
    '''

    os_name = ctx.params.get('os_name', None)
    if os_name == 'all':
        return 'all'
    if not os_name:
        fail(ctx, 'ERROR --os_name is required if --os_version is specified')

    try:
        os_versions = get_os_versions(os_name)
    except OSError as e:
        fail(ctx, 'ERROR Could not find templates for OS {}: {}'.format(os_name,
                                                                        str(e)))

    if value == 'all':
        return 'all'
    elif value not in os_versions:
        fail(ctx, 'ERROR {} is not a supported version of {}. Valid version(s): {}'.format(
            value, os_name, ', '.join(os_versions) + '.'))
    return value


def log(ctx, msg):
    '''
    '''

    if ctx.params.get('verbose', False):
        print(msg)


def fail(ctx, msg):
    '''
    '''

    print(msg)
    ctx.exit()


def get_os_version_dir(base_dir, os_name, os_version):
    '''Convenience function, returns path to template directory for this OS'''
    return path.join(base_dir, os_name, os_version, '')


def get_template_base_path(base_dir, os_name, os_version, os_template):
    '''Convenience function, returns path to template YAML file'''
    return path.join(get_os_version_dir(base_dir, os_name, os_version),
                     '{}.yaml'.format(os_template))


def get_template_base(ctx, pathname):
    '''Reads the template YAML file and returns its contents'''
    yaml = YAML()
    yaml.allow_duplicate_keys = True

    try:
        with open(pathname, 'r') as f:
            return yaml.load(f)

    except OSError as e:
        fail(ctx,
             'ERROR Unable to read YAML file {}: {}'.format(pathname, str(e)))


def get_override_variables(var_file):
    '''Open the given JSON file and return a dict of its contents'''
    try: 
        with open(var_file, 'r') as f:
            return json.load(f)
    except OSError as e:
        fail(ctx,
             'ERROR Unable to open override file {}: {}'.format(var_file, str(e)))
    except json.JSONDecodeError as e:
        fail(ctx,
             'ERROR Override file {} does not contain valid JSON: {}'.format(var_file, str(e)))


def get_templated_files(ctx, source_dir, os_template, variables_dict):
    '''Get the names of the files in source_dir to run through the template engine.
Defaults to glob(os_template.*)'''
    result = []

    if PB_TEMPLATES_KEY in variables_dict:
        for filename in variables_dict[PB_TEMPLATES_KEY]:
            if not (path.isfile(path.join(source_dir, filename))):
                fail(ctx, 'ERROR no file {} in directory {}'.format(filename, source_dir))
            result.append(filename)
        return result
        
    else:
        # Default to os_template.*
        candidates = []
        for pathname in glob(path.join(source_dir, '{}.*'.format(os_template))):
            candidates.append(path.basename(pathname))
        for candidate in candidates:
            if candidate.endswith(YAML_EXTENSIONS) or candidate.endswith(IGNORED_SUFFIXES):
                continue
            result.append(candidate)
        return result
        

def build_templates(ctx, source_dir, os_name, os_version, os_template, var_file):
    '''
    '''

    # Validate the desired working directory
    if not path.isdir(source_dir):
        fail(ctx, 'ERROR source_dir {} is not a directory'.format(
            source_dir))

    # Load the desired template's YAML file
    template_path = get_template_base_path(source_dir, os_name, os_version, os_template)
    config_dict = get_template_base(ctx, template_path)

    # Check that the result is a mapping
    if not isinstance(config_dict, Mapping):
        fail(ctx,
             'ERROR template file {} does not contain a mapping'.format(template_path))
    elif not isinstance(config_dict['variables'], Mapping):
        fail(ctx,
             'ERROR template file {} \'variables\' property is not a mapping'.format(template_path))
        
    # Drop any keys that aren't in the list of allowed Packer template keys
    # (This includes '_anchors', which is only used during YAML loading)
    for key in list(config_dict.keys()):
        if key.lower() not in PACKER_TEMPLATE_KEYS:
            del config_dict[key]

    # Attempt to bring in any variable overrides
    if var_file:
        override_dict = get_override_variables(var_file)
        config_dict['variables'].update(override_dict)

    # Create the output directory if it does not exist
    output_dir = get_os_version_dir('template', os_name, os_version)
    if not path.isdir(output_dir):
        if path.isfile(output_dir):
            fail(ctx, 'ERROR output directory {} already exists, but is a file. Aborting'.format(
                output_dir))
        makedirs(output_dir)

    # Set directories in the user variable mapping
    source_dir = get_os_version_dir(source_dir, os_name, os_version)
    config_dict['variables'][PB_SOURCE_DIR] = path.dirname(source_dir)
    config_dict['variables'][PB_TEMPLATE_DIR] = path.dirname(output_dir)

    # Set up the template engine
    renderer = Environment(loader=FileSystemLoader(source_dir))

    # Render the other destination files with the variables from the YAML file
    # (assume everything is a template)
    for file in get_templated_files(ctx, source_dir, os_template, config_dict['variables']):
        try:
            ginger = renderer.get_template(file)
        except TemplateNotFound:
            fail(ctx, 'ERROR Missing template file {}'.format(file))
        except UnicodeDecodeError:
            fail(ctx, 'ERROR Binary file {} cannot be templated'.format(file))

        target = path.join(output_dir, file)
        log(ctx, 'Writing file: {}'.format(target))
        with copen(target, 'w', 'utf-8') as f:
            f.write(ginger.render(config_dict['variables']))

    # Render the destination Packer JSON template
    # First remove the PB_TEMPLATES_KEY variable as Packer only wants strings
    del config_dict['variables'][PB_TEMPLATES_KEY]
    output_json_path = path.join(output_dir, os_template + '.json')
    log(ctx, 'Writing template: {}'.format(output_json_path))
    with copen(output_json_path, 'w', 'utf-8') as f:
        json.dump(config_dict, f,
                  sort_keys=True, indent=2, ensure_ascii=False, separators=(',', ': '))


@click.command()
@click.pass_context
@click.option('--base_dir',
              help='The base directory from which source files will be read.  Default "source".',
              default=path.join(getcwd(), 'source'),
              required=False)
@click.option('--os_name',
              help='The operating system name of the template to create.  Example "debian" or "all".  Default "all"',
              default='all',
              required=False)
# type=click.Choice(get_os_names()))
@click.option('--os_template',
              help='The name of the YAML template file to build from.  Example "base-uefi" or "all".  Default "all".',
              default='all',
              required=False)
@click.option('--os_version',
              help='The version of the operating system template to create.  Example "11_bullseye" or "all".  Default "all".',
              default='all',
              required=False)
# callback=check_os_version)
@click.option('--var_file',
              help='Extra variables JSON file to be used for template overrides before Packer runs.',
              default=False,
              required=False)
@click.option('--verbose',
              help='Enable verbose logging',
              default=False,
              is_flag=True)

def main(ctx, base_dir, os_name, os_template, os_version, var_file, verbose):
    '''
    '''

    for a_name in get_os_names(base_dir) if os_name == 'all' else [os_name]:
        for a_version in get_os_versions(base_dir, a_name) if os_version == 'all' else [os_version]:
            for a_template in get_os_templates(base_dir, a_name, a_version) if os_template == 'all' else [os_template]:
                print('Creating {} templates for {} version {}'.format(
                      a_template, a_name, a_version))
                build_templates(ctx=ctx, source_dir=base_dir,
                                os_name=a_name, os_version=a_version,
                                os_template=a_template,
                                var_file=var_file)


if __name__ == '__main__':
    main()
