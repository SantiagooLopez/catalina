import math
import re

TOKEN_PARTS = re.compile(r"\w+|[^\w\s]", re.UNICODE)


class TokenEstimator:
    def estimate(self, text: str) -> int:
        total = 0

        for part in TOKEN_PARTS.findall(text):
            if part.isalnum() or part.replace("_", "").isalnum():
                total += max(1, math.ceil(len(part) / 6))
            else:
                total += 1

        return total
