import ast
import os
import tempfile
import unittest

from py_doctor.fixer import ProjectFixer
from py_doctor.rules.fastapi_rules import InvalidRoutePathRule
from py_doctor.rules.pydantic_rules import (
    PydanticV1DumpRule,
    PydanticV1ValidatorRule,
)


class TestProjectFixer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_path = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_fix_route_paths_missing_leading_slash(self):
        code = """
@app.get("users")
def get_users():
    return []
"""
        tree = ast.parse(code)
        fixes, new_code = ProjectFixer.fix_route_paths(code, tree)
        self.assertEqual(fixes, 1)
        self.assertIn('@app.get("/users")', new_code)
        # Verify valid AST syntax
        ast.parse(new_code)
        # Verify rule no longer flags
        diags = InvalidRoutePathRule.check(ast.parse(new_code), new_code, "test.py")
        self.assertEqual(len(diags), 0)

    def test_fix_route_paths_duplicate_slashes(self):
        code = """
@app.post("//api//v1//items")
def create_item():
    pass
"""
        tree = ast.parse(code)
        fixes, new_code = ProjectFixer.fix_route_paths(code, tree)
        self.assertEqual(fixes, 1)
        self.assertIn('@app.post("/api/v1/items")', new_code)
        ast.parse(new_code)

    def test_fix_pydantic_validators(self):
        code = """
from pydantic import BaseModel, validator, root_validator

class User(BaseModel):
    name: str

    @validator("name")
    def validate_name(cls, v):
        return v

    @root_validator
    def validate_root(cls, values):
        return values
"""
        tree = ast.parse(code)
        fixes, new_code = ProjectFixer.fix_pydantic_validators(code, tree)
        self.assertEqual(fixes, 2)
        self.assertIn("@field_validator", new_code)
        self.assertIn("@model_validator", new_code)
        self.assertIn("from pydantic import BaseModel, field_validator, model_validator", new_code)
        ast.parse(new_code)
        # Verify rule no longer flags
        diags = PydanticV1ValidatorRule.check(ast.parse(new_code), new_code, "test.py")
        self.assertEqual(len(diags), 0)

    def test_fix_pydantic_dumps(self):
        code = """
from pydantic import BaseModel

class User(BaseModel):
    name: str

    def to_dict(self):
        return self.dict()

def export(user: User):
    return user.dict(exclude_unset=True)
"""
        tree = ast.parse(code)
        fixes, new_code = ProjectFixer.fix_pydantic_dumps(code, tree)
        self.assertEqual(fixes, 2)
        self.assertIn("return self.model_dump()", new_code)
        self.assertIn("user.model_dump(exclude_unset=True)", new_code)
        ast.parse(new_code)
        diags = PydanticV1DumpRule.check(ast.parse(new_code), new_code, "test.py")
        self.assertEqual(len(diags), 0)

    def test_fix_all_end_to_end(self):
        file_path = os.path.join(self.project_path, "routes.py")
        initial_content = """
from pydantic import BaseModel, validator

class UserModel(BaseModel):
    email: str

    @validator("email")
    def check_email(cls, v):
        return v

    def dump(self):
        return self.dict()

@app.get("users")
def get_users(u: UserModel):
    return u.dict(exclude_unset=True)
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(initial_content)

        fixer = ProjectFixer(self.project_path)
        stats = fixer.fix_all()

        self.assertEqual(stats["total_files_modified"], 1)
        self.assertEqual(stats["fixed_route_paths"], 1)
        self.assertEqual(stats["fixed_validators"], 1)
        self.assertEqual(stats["fixed_dumps"], 2)

        with open(file_path, encoding="utf-8") as f:
            updated_content = f.read()

        self.assertIn('@app.get("/users")', updated_content)
        self.assertIn("@field_validator", updated_content)
        self.assertIn("self.model_dump()", updated_content)
        self.assertIn("u.model_dump(exclude_unset=True)", updated_content)
        ast.parse(updated_content)


if __name__ == "__main__":
    unittest.main()
