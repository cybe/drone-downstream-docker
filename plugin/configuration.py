import os
import logging as l
import urllib.parse
from typing import NamedTuple


class Config(NamedTuple("Config",
                        [("drone_api", str), ("drone_token", str), ("gogs_api", str), ("gogs_token", str),
                         ("image", str), ("source", str)])):
    PREFIX_YAML = "PLUGIN_"
    PREFIX_ENCRYPTED = "TRIGGER_"
    DRONE_API = "DRONE_API"
    DRONE_TOKEN = "DRONE_TOKEN"
    GOGS_API = "GOGS_API"
    GOGS_TOKEN = "GOGS_TOKEN"
    IMAGE = "IMAGE"
    SOURCE = "DRONE_REPO"

    @classmethod
    def create_from_env(cls) -> "Config":
        def get_either_from_yaml_or_from_secret_store(option: str) -> str:
            return os.getenv(Config.PREFIX_YAML + option, os.getenv(Config.PREFIX_ENCRYPTED + option))

        drone_api = get_either_from_yaml_or_from_secret_store(Config.DRONE_API)
        drone_token = get_either_from_yaml_or_from_secret_store(Config.DRONE_TOKEN)
        gogs_api = get_either_from_yaml_or_from_secret_store(Config.GOGS_API)
        gogs_token = get_either_from_yaml_or_from_secret_store(Config.GOGS_TOKEN)
        image = get_either_from_yaml_or_from_secret_store(Config.IMAGE)
        source = os.getenv(Config.SOURCE)

        return cls(drone_api, drone_token, gogs_api, gogs_token, image, source)


def validate(config: Config) -> None:
    validate_value(config.drone_api, Config.DRONE_API, mandatory=True)
    validate_url(config.drone_api, Config.DRONE_API)

    validate_value(config.drone_token, Config.DRONE_TOKEN, mandatory=False,
                   additional_message="Without the token, API calls to drone won't be authenticated.")

    validate_value(config.gogs_api, Config.GOGS_API, mandatory=True)
    validate_url(config.gogs_api, Config.GOGS_API)

    validate_value(config.gogs_token, Config.GOGS_TOKEN, mandatory=False,
                   additional_message="Without the token, API calls to gogs won't be authenticated.")

    validate_value(config.image, Config.IMAGE, mandatory=True)

    validate_drone_value(config.source, Config.SOURCE)


def validate_value(value: str, option: str, mandatory: bool = False, additional_message: str = "") -> None:
    if not value:
        message = "{{}} value for {option} is missing. You {{}} declare it either in .drone.yaml " \
                  "via '{option}: some_value' or as encrypted secret '{secret}'. {addition}" \
            .format(option=option.lower(), secret=Config.PREFIX_ENCRYPTED + option, addition=additional_message)
        if mandatory:
            l.error(message.format("Mandatory", "must"))
            raise SystemExit()
        else:
            l.warning(message.format("Optional", "have the option to"))


def validate_url(url: str, corresponding_option: str) -> None:
    token = urllib.parse.urlparse(url)
    is_valid = all([getattr(token, attributes) for attributes in ('scheme', 'netloc')])
    if not is_valid:
        l.error("Invalid URL specified as %s: %s", corresponding_option.lower(), url)
        raise SystemExit()


def validate_drone_value(value: str, option: str) -> None:
    if not value:
        l.error("Mandatory environment variable {} is missing.".format(option))
        raise SystemExit()
