"""
JASVA Plugin System — Auto-loading extensibility framework.
─────────────────────────────────────────────────────────────
Drop Python files into this directory to extend JASVA's command capabilities
without modifying core code.

Each plugin must define:
    TRIGGERS      — list of compiled regex patterns (or raw strings to auto-compile)
    DESCRIPTION   — human-readable one-liner describing the plugin
    execute(text, context) -> dict  — handler returning {"status", "output", ...}

Optional:
    PRIORITY      — int (lower = checked first, default 50)
    ENABLED       — bool (default True)
    on_load()     — called once when the plugin is loaded
    on_unload()   — called when the plugin is disabled or JASVA shuts down
"""

import os
import re
import importlib
import importlib.util
import logging

logger = logging.getLogger("JASVA.plugins")

_PLUGINS_DIR = os.path.dirname(os.path.abspath(__file__))
_loaded_plugins = []   # list of plugin info dicts
_load_errors = []      # list of (filename, error_msg) tuples


class PluginInfo:
    """Container for a loaded plugin's metadata and handler."""

    __slots__ = ("name", "module", "triggers", "description", "priority",
                 "enabled", "filepath")

    def __init__(self, name, module, triggers, description, priority,
                 enabled, filepath):
        self.name = name
        self.module = module
        self.triggers = triggers          # list[re.Pattern]
        self.description = description
        self.priority = priority
        self.enabled = enabled
        self.filepath = filepath

    def matches(self, text):
        """Return True if *text* matches any of this plugin's triggers."""
        for pattern in self.triggers:
            if pattern.search(text):
                return True
        return False

    def execute(self, text, context=None):
        """Delegate to the plugin's execute() function."""
        ctx = context or {}
        return self.module.execute(text, ctx)

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "priority": self.priority,
            "enabled": self.enabled,
            "filepath": self.filepath,
            "trigger_count": len(self.triggers),
        }


def _compile_triggers(raw_triggers):
    """Accept strings or pre-compiled patterns; return list[re.Pattern]."""
    compiled = []
    for t in raw_triggers:
        if isinstance(t, re.Pattern):
            compiled.append(t)
        elif isinstance(t, str):
            try:
                compiled.append(re.compile(t, re.IGNORECASE))
            except re.error as e:
                logger.warning(f"Invalid trigger regex '{t}': {e}")
        else:
            logger.warning(f"Ignoring non-string/non-pattern trigger: {t!r}")
    return compiled


def load_plugins(directory=None):
    """Discover and load all valid plugin files from the plugins directory.

    Returns the number of successfully loaded plugins.
    """
    global _loaded_plugins, _load_errors
    _loaded_plugins = []
    _load_errors = []
    plugins_dir = directory or _PLUGINS_DIR

    if not os.path.isdir(plugins_dir):
        return 0

    count = 0
    for filename in sorted(os.listdir(plugins_dir)):
        if not filename.endswith(".py"):
            continue
        if filename.startswith("_"):  # skip __init__.py etc.
            continue

        filepath = os.path.join(plugins_dir, filename)
        module_name = f"jasva_plugin_{filename[:-3]}"

        try:
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if spec is None or spec.loader is None:
                _load_errors.append((filename, "Could not create module spec"))
                continue

            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            # Validate required attributes
            if not hasattr(mod, "TRIGGERS"):
                _load_errors.append((filename, "Missing TRIGGERS list"))
                continue
            if not hasattr(mod, "execute") or not callable(mod.execute):
                _load_errors.append((filename, "Missing execute() function"))
                continue

            triggers = _compile_triggers(mod.TRIGGERS)
            if not triggers:
                _load_errors.append((filename, "No valid triggers compiled"))
                continue

            description = getattr(mod, "DESCRIPTION", "(no description)")
            priority = getattr(mod, "PRIORITY", 50)
            enabled = getattr(mod, "ENABLED", True)
            name = getattr(mod, "NAME", filename[:-3].replace("_", " ").title())

            plugin = PluginInfo(
                name=name,
                module=mod,
                triggers=triggers,
                description=description,
                priority=priority,
                enabled=enabled,
                filepath=filepath,
            )
            _loaded_plugins.append(plugin)

            # Call on_load hook if present
            if hasattr(mod, "on_load") and callable(mod.on_load):
                try:
                    mod.on_load()
                except Exception as e:
                    logger.warning(f"Plugin '{name}' on_load() error: {e}")

            count += 1
            logger.info(f"Loaded plugin: {name} ({len(triggers)} triggers, priority={priority})")

        except Exception as e:
            _load_errors.append((filename, str(e)))
            logger.error(f"Failed to load plugin '{filename}': {e}")

    # Sort by priority (lower = checked first)
    _loaded_plugins.sort(key=lambda p: p.priority)
    logger.info(f"Plugin system: {count} loaded, {len(_load_errors)} failed")
    return count


def get_plugin_for_command(text):
    """Find the first enabled plugin whose triggers match *text*.

    Returns a PluginInfo or None.
    """
    text_lower = text.lower().strip()
    for plugin in _loaded_plugins:
        if plugin.enabled and plugin.matches(text_lower):
            return plugin
    return None


def execute_plugin_command(text, context=None):
    """Find and execute a matching plugin.

    Returns the plugin's result dict, or None if no plugin matched.
    """
    plugin = get_plugin_for_command(text)
    if plugin is None:
        return None
    try:
        logger.info(f"Plugin '{plugin.name}' handling: {text[:80]}")
        result = plugin.execute(text, context)
        if not isinstance(result, dict):
            result = {"status": "success", "output": str(result)}
        return result
    except Exception as e:
        logger.error(f"Plugin '{plugin.name}' execution error: {e}")
        return {"status": "error", "output": f"Plugin '{plugin.name}' error: {e}"}


def list_plugins():
    """Return a list of dicts describing all loaded plugins."""
    return [p.to_dict() for p in _loaded_plugins]

get_all_plugins_info = list_plugins


def get_load_errors():
    """Return a list of (filename, error_message) for plugins that failed to load."""
    return list(_load_errors)


def unload_plugins():
    """Call on_unload() hooks and clear the plugin list."""
    for plugin in _loaded_plugins:
        if hasattr(plugin.module, "on_unload") and callable(plugin.module.on_unload):
            try:
                plugin.module.on_unload()
            except Exception as e:
                logger.warning(f"Plugin '{plugin.name}' on_unload() error: {e}")
    _loaded_plugins.clear()
    _load_errors.clear()


# Auto-load plugins on import
load_plugins()
