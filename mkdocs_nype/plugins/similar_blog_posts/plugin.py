import logging
from pathlib import Path

from material.plugins.blog.plugin import BlogPlugin
from material.plugins.blog.structure import Category
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.plugins import BasePlugin, PrefixedLogger
from mkdocs.structure.files import Files
from mkdocs.structure.pages import Page

from .config import SimilarBlogPostsConfig


class SimilarBlogPostsPlugin(BasePlugin[SimilarBlogPostsConfig]):

    def __init__(self) -> None:

        self.blog_instance_map: dict[str, BlogPlugin] = {}
        self.sanitized_prefixes: list[str] = []

    def on_config(self, config: MkDocsConfig) -> MkDocsConfig | None:
        """Sanitize prefixes and load blog instances"""

        self.blog_instance_map.clear()
        self.sanitized_prefixes.clear()

        # The config value can be a str, convert it to a list
        if isinstance(self.config.hook_blog_dir, str):
            self.config.hook_blog_dir = [self.config.hook_blog_dir]

        # Prepare prefixes for synced validation
        self.sanitized_prefixes = [p.rstrip("/") + "/" for p in self.config.hook_blog_dir]

        # Load instances that have matching prefixes
        for name, instance in config.plugins.items():
            instance: BlogPlugin
            if name.split(" ")[0].endswith("/blog") and instance.config.enabled:
                blog_dir = instance.config.blog_dir.rstrip("/") + "/"
                if blog_dir in self.sanitized_prefixes:
                    self.blog_instance_map[blog_dir] = instance

        # Assert that all of the prefixes were added
        for prefix in self.sanitized_prefixes:
            if prefix not in self.blog_instance_map:
                LOG.warning(f"Prefix '{prefix}' not found among the blog instances")

        if self.blog_instance_map:
            LOG.info("Found matching blog instances")

    def on_page_markdown(
        self, markdown: str, /, *, page: Page, config: MkDocsConfig, files: Files
    ) -> str | None:
        """Add the section to a file"""

        # Ignore posts that don't have categories
        categories_self = page.meta.get("categories")
        if not categories_self:
            return

        # Use blog instance for current prefix
        for prefix in self.sanitized_prefixes:
            if page.file.src_uri.startswith(prefix):
                blog_instance = self.blog_instance_map[prefix]
                break
        else:
            return

        set_a = set(categories_self)
        similar_posts: list[Page, float] = []
        processed_post_ids = set()  # Track duplicates between categories

        # Find similar posts
        for view in blog_instance.blog.views:
            # Skip categories not related to current post
            if not isinstance(view, Category) or view.name not in set_a:
                continue

            for post in view.posts:
                # Skip self and processed
                if post is page or id(post) in processed_post_ids:
                    continue

                categories_other = post.meta.get("categories")
                set_b = set(categories_other)
                score = self.weighted_jaccard_similarity(set_a, set_b)

                if score >= self.config.similarity_threshold:
                    similar_posts.append((post, score))

                processed_post_ids.add(id(post))

        # Early return if no similar posts were found
        if not similar_posts:
            return

        # Sort posts based on score from highest to lowest
        similar_posts = sorted(similar_posts, key=lambda p: -p[1])

        # Limit the result to max_shown
        if self.config.max_shown > 0:
            similar_posts = similar_posts[: self.config.max_shown]

        posts_md = ""
        current_path = Path(page.file.abs_src_path).parent

        for post, score in similar_posts:

            url_title = post.title
            url_path = (
                Path(post.file.abs_src_path).relative_to(current_path, walk_up=True).as_posix()
            )

            posts_md += f"- [{url_title}]({url_path})\n"

        section = SECTION_TEMPLATE.format(title=self.config.title, posts_md=posts_md)

        if self.config.append_at == "end":
            markdown += "\n\n" + section
        elif self.config.append_at == "start":
            # TODO Fix h1 tag handling
            LOG.warning("H1 handling is not done")
            markdown = section + "\n\n" + markdown
        else:
            LOG.error(f"Not supported setting {self.config.append_at=}")

        return markdown

    def weighted_jaccard_similarity(
        self, set_a: set[str], set_b: set[str], use_weights: bool = True
    ) -> float:
        """Jaccard Similarity method was suggested by ChatGPT. Currently only weighted variant is being used"""

        # Sanity check
        if not set_a or not set_b:
            return 0

        # Calculate the top part of the equation
        numerator = len(set_a.intersection(set_b))

        # Use weights to handle small vs big sets a bit better
        if use_weights:
            weight_a = len(set_b) / (len(set_a) + len(set_b))
            weight_b = len(set_a) / (len(set_a) + len(set_b))
            denominator = (weight_a * len(set_a)) + (weight_b * len(set_b))
        else:
            # Calculate the bottom part of the equation
            denominator = len(set_a.union(set_b))

        return numerator / denominator


# region Constants

PLUGIN_NAME: str = "similar_blog_posts"
"""Name of this plugin. Used in logging."""

LOG: PrefixedLogger = PrefixedLogger(
    PLUGIN_NAME, logging.getLogger(f"mkdocs.plugins.{PLUGIN_NAME}")
)
"""Logger instance for this plugins."""

SECTION_TEMPLATE: str = (
    """
<div class="nype-similar" markdown>
<div class="nype-similar-title" markdown>{title}</div>
<div class="nype-similar-list" markdown>

{posts_md}

</div>
</div>
""".strip()
)

# endregion