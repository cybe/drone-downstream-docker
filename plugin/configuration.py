import os
import logging as l
import urllib.parse
from typing import NamedTuple


class Config(NamedTuple("Config",
                        [("drone_api", str), ("drone_token", str), ("gogs_api", str), ("gogs_token", str),
                         ("from_", str), ("source", str), ("dry_run", str), ("verbose", str)])):
    PREFIX_YAML = "PLUGIN_"
    PREFIX_ENCRYPTED = "TRIGGER_"
    DRONE_API = "DRONE_API"
    DRONE_TOKEN = "DRONE_TOKEN"
    GOGS_API = "GOGS_API"
    GOGS_TOKEN = "GOGS_TOKEN"
    FROM = "FROM"
    SOURCE = "DRONE_REPO"
    DRY_RUN = "DRY_RUN"
    VERBOSE = "VERBOSE"

    @classmethod
    def create_from_env(cls) -> "Config":
        def get_either_from_yaml_or_from_secret_store(option: str) -> str:
            return os.getenv(Config.PREFIX_YAML + option, os.getenv(Config.PREFIX_ENCRYPTED + option))

        def option_as_bool(option: str) -> bool:
            return bool(option) and option.lower() in ("true", "yes")

        drone_api = get_either_from_yaml_or_from_secret_store(Config.DRONE_API)
        drone_token = get_either_from_yaml_or_from_secret_store(Config.DRONE_TOKEN)
        gogs_api = get_either_from_yaml_or_from_secret_store(Config.GOGS_API)
        gogs_token = get_either_from_yaml_or_from_secret_store(Config.GOGS_TOKEN)
        from_ = get_either_from_yaml_or_from_secret_store(Config.FROM)
        source = os.getenv(Config.SOURCE)
        dry_run = option_as_bool(get_either_from_yaml_or_from_secret_store(Config.DRY_RUN))
        verbose = option_as_bool(get_either_from_yaml_or_from_secret_store(Config.VERBOSE))

        return cls(drone_api, drone_token, gogs_api, gogs_token, from_, source, dry_run, verbose)


def validate(config: Config) -> None:
    validate_value(config.drone_api, Config.DRONE_API, mandatory=True)
    validate_url(config.drone_api, Config.DRONE_API)

    validate_value(config.drone_token, Config.DRONE_TOKEN, mandatory=False,
                   additional_message="Without the token, API calls to drone won't be authenticated.")

    validate_value(config.gogs_api, Config.GOGS_API, mandatory=True)
    validate_url(config.gogs_api, Config.GOGS_API)

    validate_value(config.gogs_token, Config.GOGS_TOKEN, mandatory=False,
                   additional_message="Without the token, API calls to gogs won't be authenticated.")

    validate_value(config.from_, Config.FROM, mandatory=True)

    validate_drone_value(config.source, Config.SOURCE)


def validate_value(value: str, option: str, mandatory: bool = False, additional_message: str = "") -> None:
    if not value:
        message = "{{}} value for {option} is missing. You {{}} declare it either in .drone.yml " \
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
