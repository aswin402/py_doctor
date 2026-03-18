from .base_rule import BaseRule

class MissingSessionCloseRule(BaseRule):
    rule_id = 'sqlalchemy/missing-session-close'
    severity = 'ERR'

    @classmethod
    def check(cls, tree, source, rel_path):
        # Detect session.close() missing
        return []

class NoSessionScope(BaseRule):
    rule_id = 'sqlalchemy/no-session-scope'
    severity = 'WARN'

    @classmethod
    def check(cls, tree, source, rel_path):
        return []
