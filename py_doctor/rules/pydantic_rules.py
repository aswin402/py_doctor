from .base_rule import BaseRule

class UnsafeField(BaseRule):
    rule_id = 'pydantic/unsafe-field'
    severity = 'WARN'

    @classmethod
    def check(cls, tree, source, rel_path):
        return []

class MissingValidator(BaseRule):
    rule_id = 'pydantic/missing-validator'
    severity = 'WARN'

    @classmethod
    def check(cls, tree, source, rel_path):
        return []
