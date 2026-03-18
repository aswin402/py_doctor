from .base_rule import BaseRule

class PrintInsteadLog(BaseRule):
    rule_id = 'structlog/print-instead-of-log'
    severity = 'WARN'

    @classmethod
    def check(cls, tree, source, rel_path):
        return []
