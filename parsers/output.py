from typing import Optional

class Result:
    _fields = ['company_name', 'position', 'application_link', 'description', 'company_size']

    def __init__(self, parser_type: Optional[str] = None, **kwargs):
        self.parser_type = parser_type
        self.company_name = kwargs.get('company_name')
        self.position = kwargs.get('position')
        self.application_link = kwargs.get('application_link', [None] * len(self.company_name))
        self.description = kwargs.get('description', [None] * len(self.company_name))
        self.company_size = kwargs.get('company_size', [None] * len(self.company_name))

    def __repr__(self):
        return (f"Result(company_name={self.company_name!r}, "
                f"position={self.position!r}, "
                f"application_link={self.application_link!r}, "
                f"description={self.description!r})")

    def values(self):
        """Return all field values as lists"""
        return [getattr(self, field) for field in self._fields]

    def keys(self):
        """Return all field names"""
        return self._fields