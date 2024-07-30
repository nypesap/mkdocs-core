from mkdocs.config import Config
from mkdocs.config.config_options import Choice, ListOfItems, Optional, Type


class CustomCallToActionSectionsConfig(Config):

    enabled = Type(bool, default=True)

    paths = ListOfItems(Type(str))
    """List of string relative paths to directories or files. Can start with docs/, but don't have to."""

    append_at = Choice(("start", "end"), default="end")
    section_cta = Type(str)
    section_target = Type(str)
    section_title = Type(str)
    section_type = Choice(("title_and_cta",), default="title_and_cta")
