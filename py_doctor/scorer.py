def calculate_score(errors: int, warnings: int, dead_code: int) -> int:
    score = 100 - (errors * 3) - warnings - dead_code
    return max(0, min(100, score))
