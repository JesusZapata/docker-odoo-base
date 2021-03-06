# -*- coding: utf-8 -*-
import logging
import os
from glob import iglob

import yaml

# Constants needed in scripts
CUSTOM_DIR = "/opt/odoo/custom"
SRC_DIR = os.path.join(CUSTOM_DIR, 'src')
ADDONS_YAML = os.path.join(SRC_DIR, 'addons')
if os.path.isfile('%s.yaml' % ADDONS_YAML):
    ADDONS_YAML = '%s.yaml' % ADDONS_YAML
else:
    ADDONS_YAML = '%s.yml' % ADDONS_YAML
ADDONS_DIR = "/opt/odoo/auto/addons"
CLEAN = os.environ.get("CLEAN") == "true"
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
FILE_APT_BUILD = os.path.join(
    CUSTOM_DIR, 'dependencies', 'apt_build.txt',
)
PRIVATE = "private"
CORE = "odoo/addons"
PRIVATE_DIR = os.path.join(SRC_DIR, PRIVATE)
CORE_DIR = os.path.join(SRC_DIR, CORE)

# Customize logging for build
logging.root.name = "docker-odoo-base"
_log_level = os.environ.get("LOG_LEVEL", "")
if _log_level.isdigit():
    _log_level = int(_log_level)
elif _log_level in LOG_LEVELS:
    _log_level = getattr(logging, _log_level)
else:
    if _log_level:
        logging.warning("Wrong value in $LOG_LEVEL, falling back to INFO")
    _log_level = logging.INFO
logging.root.setLevel(_log_level)


def addons_config():
    """Yield addon name and path from ``ADDONS_YAML``."""
    config = dict()
    private_done = False
    core_done = False
    try:
        with open(ADDONS_YAML) as addons_file:
            for doc in yaml.load_all(addons_file):
                # Skip sections with ONLY and that don't match
                if any(os.environ.get(key) not in values
                       for key, values in doc.get("ONLY", dict()).items()):
                    logging.debug("Skipping section with ONLY %s", doc["ONLY"])
                    continue
                # Flatten all sections in a single dict
                for repo, addons in doc.items():
                    if repo == PRIVATE:
                        private_done = True
                    elif repo == CORE:
                        core_done = True
                    logging.debug("Processing %s repo", repo)
                    for glob in addons:
                        logging.debug("Expanding glob %s", glob)
                        for addon in iglob(os.path.join(SRC_DIR, repo, glob)):
                            logging.debug("Registering addon %s", addon)
                            addon = os.path.basename(addon)
                            config.setdefault(addon, set())
                            config[addon].add(repo)
    except IOError:
        logging.debug('Could not find addons configuration yml.')
    # By default, all private and core addons are enabled
    if not private_done:
        logging.debug("Auto-adding all private repo addons")
        config.update({
            os.path.basename(addon): {PRIVATE}
            for addon in iglob(os.path.join(SRC_DIR, PRIVATE, "*"))
        })
    if not core_done:
        logging.debug("Auto-adding all core repo addons")
        config.update({
            os.path.basename(addon): {CORE}
            for addon in iglob(os.path.join(SRC_DIR, CORE, "*"))
        })
    logging.debug("Resulting configuration: %r", config)
    for addon, repos in config.items():
        # Private addons are most important
        if PRIVATE in repos:
            yield addon, PRIVATE
        # Odoo core addons are least important
        elif repos == {CORE}:
            yield addon, CORE
        # Other addons fall in between
        elif len(repos) != 1:
            logging.error("Addon %s defined in several repos %s", addon, repos)
            raise Exception
        else:
            yield addon, repos.pop()
