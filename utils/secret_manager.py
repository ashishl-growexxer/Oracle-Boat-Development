import os
from configparser import ConfigParser
from logger_config import logger

class SecretManager:
    def __init__(self):
        self.config = ConfigParser()
        self.config.read('config1.ini')

    def get_secret(self, default=None):
        try:
            login_username = self.config.get('AUTH','USERNAME')
            login_password = self.config.get('AUTH','PASSWORD')
            adw_username = self.config.get('ADW','USERNAME')
            adw_password = self.config.get('ADW','PASSWORD')

            # Fallback to local config file
            return {
                "login_username":login_username,
                "login_password":login_password,
                "adw_username":adw_username,
                "adw_password":adw_password
            }
        except Exception as e:
            logger.error(f"Failed to retrieve secret: usernames and passwords -> {e}")
            return default
