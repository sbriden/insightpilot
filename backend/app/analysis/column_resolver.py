class ColumnResolver:

    def __init__(self, column_profiles):
        self.columns = column_profiles

    def find(
        self,
        role=None,
        keywords=None,
    ):

        keywords = keywords or []

        # Keyword match first
        if keywords:

            for column in self.columns:

                name = column["name"].lower()

                if any(
                    keyword in name
                    for keyword in keywords
                ):
                    return column["name"]

        # Fallback to role
        if role:

            for column in self.columns:

                if column["role"] == role:
                    return column["name"]

        return None


    def customer(self):
        return self.find(
            keywords=["customer"]
        )


    def sales(self):
        return self.find(
            keywords=["sales", "revenue"]
        )


    def profit(self):
        return self.find(
            keywords=["profit"]
        )


    def date(self):
        return self.find(
            role="date"
        )


    def category(self):
        return self.find(
            keywords=["category"]
        )


    def region(self):
        return self.find(
            keywords=["region", "state"]
        )


    def product(self):
        return self.find(
            keywords=["product"]
        )