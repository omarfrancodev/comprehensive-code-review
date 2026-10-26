"""Pure purpose validation shared by checks and capture receipts."""


def purpose_errors(value: object, field: str) -> list[str]:
    if (not isinstance(value, str) or not value.strip() or len(value) > 4000
            or any(ord(character) < 32 for character in value)):
        return [field + ': nonempty purpose (maximum 4000 characters, no controls) required']
    return []
