from configparser import SafeConfigParser
import os

config = SafeConfigParser()
config.read(['diskripper.conf', os.path.expanduser('~/.config/diskripper.conf')])


def configure(app):
    """Configures the app based on the config file it read"""
    for key in config['flask']:
        app.config[key.upper()] = config['flask'][key]

    for section in config:
        if section != 'flask':
            app.config[section] = {}
            for key in config[section]:
                app.config[section][key] = config[section][key]
