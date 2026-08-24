import re
from typing import Optional, Tuple
from app.executive.roles import ExecutiveRole

class ExecutiveRouter:
    """
    Parses executive commands (@CEO, @COO, @CFO, @CMO, @CTO, @5C) from user prompts
    and routes them to appropriate single or council workflows.
    """

    COMMAND_MAP = {
        "@ceo": ExecutiveRole.CEO,
        "@coo": ExecutiveRole.COO,
        "@cfo": ExecutiveRole.CFO,
        "@cmo": ExecutiveRole.CMO,
        "@cto": ExecutiveRole.CTO,
    }

    @classmethod
    def parse_command(cls, prompt: str) -> Tuple[Optional[ExecutiveRole], bool, str]:
        """
        Returns:
            (role, is_5c_council, clean_prompt)
        """
        stripped = prompt.strip()
        
        # Check for @5C or @5c
        if re.match(r'^@5c\b', stripped, re.IGNORECASE):
            clean = re.sub(r'^@5c\s*', '', stripped, flags=re.IGNORECASE).strip()
            return None, True, clean

        # Check for single role commands @CEO, @COO, etc.
        for cmd, role in cls.COMMAND_MAP.items():
            if re.match(rf'^{cmd}\b', stripped, re.IGNORECASE):
                clean = re.sub(rf'^{cmd}\s*', '', stripped, flags=re.IGNORECASE).strip()
                return role, False, clean

        return None, False, stripped
