from bot.handlers.start import register_start_handlers
from bot.handlers.check import register_check_handlers
from bot.handlers.learn import register_learn_handlers
from bot.handlers.profile import register_profile_handlers


def register_all_handlers(app):
    """Register all bot handlers."""
    register_start_handlers(app)
    register_check_handlers(app)
    register_learn_handlers(app)
    register_profile_handlers(app)
